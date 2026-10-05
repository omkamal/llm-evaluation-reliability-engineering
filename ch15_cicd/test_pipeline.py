"""Run records, the baseline, the Friday pull request end to end, the
gate's own test, flaky cases, the cache, bisect and the guard."""
import json
import random
import shutil
import tempfile
from pathlib import Path

import pytest

from ch15_cicd import (budget, check, demo, flaky, gate, guard, history,
                       record, repo, run_tier, suite)
from ch15_cicd.tiers import TIERS, Tier


# --- the run record ------------------------------------------------------
def test_a_run_carries_every_version_that_produced_it():
    results = run_tier.run_tier("smoke", seed=1)
    rec = results["record"]
    assert rec["prompt"] == "system@7" and rec["model"] == "a-large-v1"
    assert rec["tools"] == ["reschedule_delivery@2", "reset_password@1"]
    assert rec["index"] == "policy-index v3" and rec["judge"] == "judge_v2"
    assert rec["eval_set"].startswith("Relay gate set v1 (")


def test_the_eval_set_label_changes_when_a_case_is_added():
    cases = suite.case_meta()
    extra = {"id": "INC2-1", "slice": "non-trigger", "never_fail": False,
             "text": "My parcel is late, where is it?"}
    assert (record.eval_set_label(1)
            != record.eval_set_label(2, cases + [extra]))
    assert record.eval_set_label(1) == record.eval_set_label(1, cases)


def test_the_record_prints_as_six_lines():
    lines = record.lines(run_tier.run_tier("smoke")["record"])
    assert [l.split()[0] for l in lines] == [
        "prompt", "model", "tools", "index", "eval", "judge"]
    assert all(len(l) <= 74 for l in lines)


# --- the baseline --------------------------------------------------------
def test_the_committed_baseline_is_what_main_produces():
    committed = json.loads(run_tier.BASELINE.read_text())
    fresh = run_tier.run_tier("release", seed=1)
    assert committed == json.loads(json.dumps(fresh))


def test_the_baseline_covers_every_case_with_five_trials():
    cases = json.loads(run_tier.BASELINE.read_text())["cases"]
    assert len(cases) == 90
    assert {len(c["trials"]) for c in cases.values()
            if not c["never_fail"]} == {5}
    assert {len(c["trials"]) for c in cases.values()
            if c["never_fail"]} == {20}


def test_a_run_is_deterministic_and_a_smoke_run_has_50_cases():
    a = run_tier.run_tier("smoke", seed=5)
    assert a == run_tier.run_tier("smoke", seed=5)
    assert len(a["cases"]) == 50
    assert a["cases"] != run_tier.run_tier("smoke", seed=6)["cases"]


def test_command_line_writes_results_and_baseline(tmp_path, capsys):
    out = tmp_path / "scores.json"
    assert run_tier.main(["--sample", "50", "--seed", "2",
                          "--out", str(out)]) == 0
    assert len(json.loads(out.read_text())["cases"]) == 50
    assert "50 cases, 1 trials" in capsys.readouterr().out


# --- the scripted builds -------------------------------------------------
def test_scripted_builds_use_the_real_graders():
    assert sum(suite.scripted("main")) == 28 + 54
    assert sum(suite.scripted("friday")) == 23 + 51


def test_the_friday_build_fails_two_never_fail_cases():
    never = [c["id"] for c in suite.case_meta() if c["never_fail"]]
    right = dict(zip([c["id"] for c in suite.case_meta()],
                     suite.scripted("friday")))
    assert [i for i in never if not right[i]] == ["T3.5", "T3.9"]


# --- the Friday pull request, end to end -----------------------------------
def friday_gate(tier, seed=3):
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        root = demo.friday_pull_request(tmp)
        results = run_tier.run_tier(tier, root=root, seed=seed)
        run_tier.write(results, tmp / "scores.json")
        base = json.loads(run_tier.BASELINE.read_text())
        return gate.decide(base["cases"], results["cases"],
                           *check.load_rules()[:1],
                           min_cases=20, resamples=1000), results


def test_a_well_formed_friday_pull_request_still_gets_blocked():
    files = demo.friday_files(repo.snapshot(), bump=True, changelog=True)
    assert repo.check_change(repo.snapshot(), files) == []   # review OK
    result, results = friday_gate("full")
    assert results["record"]["prompt"] == "system@8"
    assert result["verdict"] == "BLOCK"
    assert set(result["floor"]["failed"]) == {"T3.5", "T3.9"}


def test_the_unchanged_main_build_is_not_blocked_at_full_strength():
    with tempfile.TemporaryDirectory() as raw:
        results = run_tier.run_tier("full", seed=3)
        base = json.loads(run_tier.BASELINE.read_text())
        result = gate.decide(base["cases"], results["cases"],
                             *check.load_rules()[:1], min_cases=20,
                             resamples=1000)
    assert result["verdict"] != "BLOCK"


# --- the gate's own test (the numbers printed in the chapter) --------------
def test_an_unchanged_build_is_almost_never_blocked():
    for tier in TIERS:
        counts = check.verdict_counts("main", tier)
        assert counts["BLOCK"] <= 1
    assert check.verdict_counts("main", "smoke") == {"WARN": 86, "PASS": 14}


def test_the_friday_tweak_is_blocked_at_every_tier():
    assert check.verdict_counts("friday", "smoke")["BLOCK"] == 97
    assert check.verdict_counts("friday", "full")["BLOCK"] == 100
    assert check.verdict_counts("friday", "release")["BLOCK"] == 100


def test_at_smoke_strength_the_never_fail_rule_does_the_work():
    alone = check.verdict_counts("friday", "smoke", floor=False)
    assert alone["BLOCK"] == 34


def test_a_gate_that_blocks_on_doubt_blocks_nearly_every_healthy_build():
    strict = check.verdict_counts("main", "full", on_unsure="block")
    assert strict["BLOCK"] == 100


def test_chapter_3s_hard_line_blocks_healthy_builds_about_half_the_time():
    blocks = [check.hard_line_blocks("main", t) for t in TIERS]
    assert blocks == [56, 60, 63]


def test_a_two_point_margin_is_below_what_90_cases_can_resolve():
    lows = check.lower_bounds("main", "full")
    assert round(lows[4], 3) == -0.069          # 95 of 100 lie above
    shares = [sum(low >= -m for low in lows) for m in (0.02, 0.05, 0.08)]
    assert shares == [13, 71, 99]


# --- flaky cases -----------------------------------------------------------
def repeated_runs(seed=4, runs=10, trials=5):
    rng = random.Random(seed)
    return [suite.run_trials("main", trials, rng) for _ in range(runs)]


def test_the_flaky_detector_finds_the_borderline_cases_and_no_others():
    found = flaky.flaky_cases(repeated_runs())
    assert sorted(found) == sorted(suite.BORDERLINE)


def test_a_steady_failure_is_not_flaky():
    rates = flaky.pooled_rates(repeated_runs())
    assert rates["R-02"] < 0.4            # fails steadily: a real failure
    assert "R-02" not in flaky.flaky_cases(repeated_runs())


def test_a_quarantine_expires():
    run = repeated_runs(runs=1)[0]
    quarantine = {"R-12": {"owner": "Priya", "until": "2026-10-02"}}
    kept, held = flaky.apply_quarantine(run, quarantine, "2026-09-28")
    assert held == ["R-12"] and "R-12" not in kept
    kept, held = flaky.apply_quarantine(run, quarantine, "2026-10-05")
    assert held == [] and "R-12" in kept


# --- cost, cache ---------------------------------------------------------
def test_the_small_tier_is_cheaper_on_every_line():
    assert budget.trial_cost("a-small") < budget.trial_cost("a-large")
    assert (budget.run_cost("a-small", 270, budget.JUDGE)
            < budget.run_cost("a-large", 270, budget.JUDGE))
    assert budget.PRICES["a-small"][0] < budget.PRICES["a-large"][0]
    assert budget.PRICES["a-small"][1] < budget.PRICES["a-large"][1]


def test_the_cache_pays_once_per_key():
    cache = budget.ResultCache()
    key = cache.key("m", "p", "s", "R-01", 0)
    assert cache.get(key, lambda: 41) == 41
    assert cache.get(key, lambda: 99) == 41
    assert (cache.hits, cache.misses) == (1, 1)


def test_every_trial_has_its_own_key_or_noise_disappears():
    keys = {budget.ResultCache.key("m", "p", "s", "R-01", t)
            for t in range(5)}
    assert len(keys) == 5


def test_a_prompt_or_schema_edit_invalidates_the_cache():
    base = budget.ResultCache.key("m", "system@7", "s1", "R-01", 0)
    assert base != budget.ResultCache.key("m", "system@8", "s1", "R-01", 0)
    assert base != budget.ResultCache.key("m", "system@7", "s2", "R-01", 0)
    assert base != budget.ResultCache.key("m2", "system@7", "s1", "R-01", 0)


# --- bisect ----------------------------------------------------------------
@pytest.mark.parametrize("culprit", range(8))
def test_bisect_finds_any_culprit_among_eight_in_three_evals(culprit):
    changes = list(range(8))
    found, runs = history.bisect(changes, lambda done: culprit in done)
    assert (found, runs) == (culprit, 3)


def test_bisect_of_one_change_needs_no_eval():
    assert history.bisect(["only"], lambda done: True) == ("only", 0)


def test_bisect_with_the_real_gate_finds_the_friday_sentence(capsys):
    demo.show_bisect()
    out = capsys.readouterr().out
    assert "culprit: prompt 9: be more proactive" in out
    assert "found in 3 evals, not 8" in out


# --- the contamination guard -------------------------------------------------
def test_the_committed_prompt_has_no_leaks():
    assert guard.check(repo.snapshot()["prompts/system.md"]) == []
    assert guard.main() == 0


def test_a_pasted_test_question_is_a_leak():
    text = repo.snapshot()["prompts/system.md"]
    text += "Example: Can I send something back after two weeks?\n"
    assert guard.check(text) == [("R-02", "prompt", 1.0)]


def test_the_guard_reads_the_judge_examples_from_the_repository(tmp_path):
    root = tmp_path / "relay"
    shutil.copytree(repo.ROOT, root)
    assert guard.main(root) == 0
    examples = root / "evals" / "judge_examples.txt"
    examples.write_text(examples.read_text()
                        + "\nCustomer: Reset my password, please\n")
    assert guard.main(root) == 1


def test_a_judge_example_can_leak_too():
    leaks = guard.check(repo.snapshot()["prompts/system.md"],
                        ["Reset my password, please", ])
    assert any(where == "judge_example_1" for _, where, _ in leaks)


def test_a_neutral_change_needs_577_cases_to_clear_two_points():
    from math import ceil
    assert ceil(1.96 ** 2 * 0.06 / 0.02 ** 2) == 577
