"""Prompts as code, the path filter, the tiers and the workflow file."""
import json
import re
from pathlib import Path

import pytest

from ch15_cicd import budget, repo
from ch15_cicd.demo import friday_files
from ch15_cicd.tiers import (SAFETY_TRIALS, TIERS, TRIGGER_PATHS,
                             needs_evals, pick_sample)

WORKFLOW = Path(__file__).parent / "workflows" / "evals.yml"
GITHUB = Path(__file__).parent.parent / ".github" / "workflows"


# --- the repository ----------------------------------------------------
def test_the_prompt_file_has_a_version_and_an_owner():
    header, body = repo.read_prompt(repo.snapshot()["prompts/system.md"])
    assert header["version"] == 7 and header["owner"] == "Sam"
    assert body.startswith("You are Relay")


def test_the_committed_repository_has_no_review_problems():
    files = repo.snapshot()
    assert repo.check_change(files, files) == []


def test_friday_as_first_written_is_caught_in_review():
    main = repo.snapshot()
    assert repo.check_change(main, friday_files(main)) == [
        "prompt text changed, version still 7"]


def test_a_version_bump_needs_a_changelog_line():
    main = repo.snapshot()
    bumped = friday_files(main, bump=True)
    assert repo.check_change(main, bumped) == [
        "no CHANGELOG line for version 8"]
    full = friday_files(main, bump=True, changelog=True)
    assert repo.check_change(main, full) == []


def test_a_floating_model_name_is_not_a_pinned_snapshot():
    main = repo.snapshot()
    alias = dict(main)
    alias["config/relay.json"] = main["config/relay.json"].replace(
        "a-large-v1", "a-large-latest")
    assert "not a pinned snapshot" in repo.check_change(main, alias)[0]
    pinned = dict(main)
    pinned["config/relay.json"] = main["config/relay.json"].replace(
        "a-large-v1", "a-large-v2")
    assert repo.check_change(main, pinned) == []     # a one-line upgrade


def test_one_sentence_changes_the_whole_feature():
    files = repo.snapshot()
    assert repo.build_of(files["prompts/system.md"]) == "main"
    tweaked = friday_files(files)["prompts/system.md"]
    assert repo.build_of(tweaked) == "friday"


def test_tool_versions_and_schema_hash():
    assert repo.tool_versions() == ["reschedule_delivery@2",
                                    "reset_password@1"]
    assert len(repo.schema_hash()) == 8


# --- the path filter -----------------------------------------------------
@pytest.mark.parametrize("path,expected", [
    ("README.md", False),
    ("docs/prompts/notes.md", False),
    ("ch15_cicd/relay/prompts/system.md", True),
    ("ch15_cicd/relay/config/relay.json", True),
    ("ch15_cicd/relay/schemas/reset_password.json", True),
    ("ch15_cicd/relay/evals/thresholds.json", True),
    ("ch15_cicd/relay/PROMPT_CHANGE.md", False),
    ("ch15_cicd/gate.py", True),                  # the judge of the PR
    ("requirements-dev.txt", True),
    (".github/workflows/evals.yml", True),
    (".github/workflows/tests.yml", False),
])
def test_only_files_that_change_behaviour_trigger_evals(path, expected):
    assert needs_evals([path]) is expected


def test_one_matching_file_is_enough():
    assert needs_evals(["README.md", "ch15_cicd/relay/config/a.json"])


# --- tiers ---------------------------------------------------------------
def ids(n=90):
    return [f"c{i:02d}" for i in range(n)]


def test_smoke_sample_is_50_cases_and_keeps_every_never_fail_case():
    never = {"c03", "c04", "c88"}
    chosen = pick_sample(ids(), never, 50, seed=1)
    assert len(chosen) == 50 and never <= set(chosen)


def test_smoke_sample_is_repeatable_and_rotates():
    first = pick_sample(ids(), set(), 50, seed=1)
    assert first == pick_sample(ids(), set(), 50, seed=1)
    assert first != pick_sample(ids(), set(), 50, seed=2)


def test_a_full_run_takes_everything():
    assert pick_sample(ids(), set(), None, seed=1) == ids()


def test_the_three_tiers_match_the_workflow_flags():
    assert TIERS["smoke"].sample == 50 and TIERS["smoke"].trials == 1
    assert TIERS["full"].trials == 3 and TIERS["full"].sample is None
    assert TIERS["release"].trials == 5 and TIERS["release"].safety
    assert TIERS["release"].safety_trials == SAFETY_TRIALS == 20
    assert TIERS["smoke"].safety_trials == 0


def test_tier_costs_and_budgets():
    assert budget.run_cost("a-large", 50) == pytest.approx(1.0125)
    assert budget.within_budget("smoke", budget.run_cost("a-large", 50))
    assert not budget.within_budget(
        "full", budget.run_cost("a-large", 500 * 3))


# --- the workflow file ---------------------------------------------------
def load_workflow():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(WORKFLOW.read_text())


def test_the_workflow_parses_and_has_the_three_triggers():
    flow = load_workflow()
    on = flow.get("on", flow.get(True))        # YAML reads `on` as True
    assert set(on) == {"pull_request", "schedule", "push",
                       "workflow_dispatch"}
    assert on["schedule"] == [{"cron": "17 3 * * *"}]   # off the hour
    assert on["push"]["tags"] == ["v*"]


def test_the_workflow_path_filter_matches_the_python_one():
    flow = load_workflow()
    on = flow.get("on", flow.get(True))
    assert tuple(on["pull_request"]["paths"]) == TRIGGER_PATHS


def test_the_workflow_runs_each_tier_with_the_right_flags():
    text = WORKFLOW.read_text()
    assert "run_tier --sample 50" in text
    assert "run_tier --trials 3 --check-baseline" in text
    assert "run_tier --trials 5 --safety" in text
    assert "ch15_cicd.guard" in text and "ch15_cicd.gate" in text


def test_the_workflow_keeps_the_report_even_when_the_gate_blocks():
    steps = load_workflow()["jobs"]["evals"]["steps"]
    gate_step = next(s for s in steps if s.get("name") == "Gate")
    assert gate_step["shell"] == "bash"          # bash runs with pipefail
    assert "tee results/report.md" in gate_step["run"]
    after = steps[steps.index(gate_step) + 1:]
    # !cancelled(), not always(): a stale run that was cancelled must
    # not overwrite the newer run's comment.
    assert after and all("!cancelled()" in s["if"] for s in after)
    assert "always()" not in WORKFLOW.read_text()


def test_the_workflow_has_least_privilege_and_a_time_limit():
    flow = load_workflow()
    assert flow["permissions"] == {"contents": "read",
                                   "pull-requests": "write"}
    limit = flow["jobs"]["evals"]["timeout-minutes"]
    assert "'pull_request' && 15 || 120" in limit    # smoke, or the rest
    assert flow["concurrency"]["cancel-in-progress"] is True
    assert "github.event_name" in flow["concurrency"]["group"]


def test_the_comment_step_skips_pull_requests_from_forks():
    steps = load_workflow()["jobs"]["evals"]["steps"]
    step = next(s for s in steps if "Comment" in s.get("name", ""))
    assert "head.repo.full_name == github.repository" in step["if"]


SHA = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


def workflows():
    found = [WORKFLOW] + sorted(GITHUB.glob("*.yml"))
    return [p for p in found if p.exists()]


def test_runners_and_actions_are_pinned():
    yaml = pytest.importorskip("yaml")
    for path in workflows():
        for job in yaml.safe_load(path.read_text())["jobs"].values():
            assert job["runs-on"] == "ubuntu-24.04", path
            for step in job["steps"]:
                if "uses" in step:
                    assert SHA.match(step["uses"]), (path, step["uses"])


def test_the_workflow_github_runs_is_the_one_in_the_chapter():
    live = GITHUB / "evals.yml"
    if not live.exists():
        pytest.skip("no .github folder in this copy")
    assert live.read_text() == WORKFLOW.read_text()


def test_packages_are_pinned_to_exact_versions():
    root = Path(__file__).parent.parent
    for name in ("requirements.txt", "requirements-dev.txt"):
        for line in (root / name).read_text().splitlines():
            if line and not line.startswith("-r"):
                assert re.fullmatch(r"[\w-]+==[\d.]+", line), line


def test_thresholds_file_matches_the_chapter():
    cfg = json.loads((repo.ROOT / "evals/thresholds.json").read_text())
    margins = {r["slice"]: r["margin"] for r in cfg["rules"]}
    assert margins == {"all": 0.02, "policy": 0.03, "trigger": 0.05,
                       "non-trigger": 0.02}
    assert cfg["min_cases"] == 20
