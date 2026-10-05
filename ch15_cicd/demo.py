"""Every output printed in Chapter 15.   python -m ch15_cicd.demo"""
import random
import shutil
import tempfile
from pathlib import Path

from ch07_datasets.sandbox import LiveTenantError
from ch15_cicd import (budget, check, flaky, gate, guard, history, record,
                       repo, run_tier, suite)
from ch15_cicd.tiers import TIERS, needs_evals, pick_sample

PURPOSE = {
    "prompts/system.md": "the prompt, with its version",
    "prompts/CHANGELOG.md": "one line per version",
    "schemas/reschedule_delivery.json": "a tool contract",
    "schemas/reset_password.json": "a tool contract",
    "config/relay.json": "pinned model, index, judge",
    "evals/judge_examples.txt": "the judge's worked examples",
    "evals/thresholds.json": "margins and slice limits",
    "evals/baseline/main.json": "main's scores, per case",
    "PROMPT_CHANGE.md": "the change request template",
}
FRIDAY = ("Be more proactive: take the next helpful step without "
          "waiting to be asked.\n")


def say(text=""):
    print(text)


def show_layout():
    say("relay/")
    for path in sorted(repo.ROOT.rglob("*")):
        rel = str(path.relative_to(repo.ROOT))
        if path.is_file():
            say(f"  {rel:<34}{PURPOSE[rel]}")


def friday_files(files, bump=False, changelog=False):
    """Main's files with the Friday sentence added, as a pull request."""
    new = dict(files)
    text = files["prompts/system.md"]
    if bump:
        text = text.replace("version: 7", "version: 8")
    new["prompts/system.md"] = text.replace(
        "Never reset", FRIDAY + "Never reset")
    if changelog:
        new["prompts/CHANGELOG.md"] = files["prompts/CHANGELOG.md"].replace(
            "\n7   ", "\n8   2026-10-02  Sam    Be more proactive\n7   ")
    return new


def show_review():
    main = repo.snapshot()
    steps = [("as first written", friday_files(main)),
             ("version bumped", friday_files(main, bump=True)),
             ("changelog added",
              friday_files(main, bump=True, changelog=True))]
    for label, files in steps:
        problems = repo.check_change(main, files) or ["no problems"]
        say(f"{label}: {'; '.join(problems)}")
    alias = dict(main)
    alias["config/relay.json"] = main["config/relay.json"].replace(
        "a-large-v1", "a-large-latest")
    say(f"model alias: {repo.check_change(main, alias)[0]}")


def show_paths():
    for path in ("README.md", "ch15_cicd/relay/prompts/system.md",
                 "ch15_cicd/relay/config/relay.json",
                 "ch15_cicd/relay/PROMPT_CHANGE.md"):
        say(f"{path:<38}{'run evals' if needs_evals([path]) else 'skip'}")


def show_tiers():
    meta = suite.case_meta()
    never = {c["id"] for c in meta if c["never_fail"]}
    say("tier     cases  trials  runs    cost  budget")
    for name, tier in TIERS.items():
        ids = pick_sample([c["id"] for c in meta], never, tier.sample, 0)
        runs = sum(tier.safety_trials or tier.trials if i in never
                   else tier.trials for i in ids)
        cost = budget.run_cost("a-large", runs)
        say(f"{name:<8}{len(ids):>5}{tier.trials:>8}{runs:>6}"
            f"{'$%.2f' % cost:>8}{'$%.2f' % budget.BUDGETS[name]:>8}")
    big = budget.run_cost("a-large", 500 * 3)
    ok = "within" if budget.within_budget("full", big) else "over"
    say(f"full tier on 500 cases: ${big:.2f}, {ok} its "
        f"${budget.BUDGETS['full']:.2f} budget")
    for model in ("a-large", "a-small"):
        cost = budget.run_cost(model, 270, budget.JUDGE)
        say(f"judging 270 answers with {model}: ${cost:.2f}")


def show_worked_examples():
    say("200 cases, 159 right on main (constructed outcomes)")
    say("better worse  change  95% interval      warn rule  block rule")
    for better, worse in ((9, 4), (6, 6), (7, 10)):
        main, change = suite.paired_outcomes(better, worse)
        got = []
        for on_unsure in ("warn", "block"):
            rule = gate.Rule("all", 0.02, on_unsure)
            got.append(gate.decide(main, change, [rule]))
        row = got[0]["rows"][0]
        say(f"{better:>5}{worse:>6}  {row['delta']:+.3f}  "
            f"[{row['lo']:+.3f}, {row['hi']:+.3f}]  "
            f"{got[0]['verdict']:<10} {got[1]['verdict']}")


def show_floor_bounds():
    say("never-fail trials with no failure: failure rate below")
    for n in (10, 20, 59):
        say(f"{n:>3} trials: {gate.floor_bound(n):.2%}")


def friday_pull_request(tmp):
    """The Friday tweak as a complete, well-formed pull request."""
    root = tmp / "relay"
    shutil.copytree(repo.ROOT, root)
    files = friday_files(repo.snapshot(), bump=True, changelog=True)
    for rel in ("prompts/system.md", "prompts/CHANGELOG.md"):
        (root / rel).write_text(files[rel])
    return root


def show_tenant():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw) / "relay"
        shutil.copytree(repo.ROOT, root)
        config = root / "config/relay.json"
        config.write_text(config.read_text().replace(
            '"eval-ci", "kind": "test"', '"parcelpath-prod", "kind": "live"'))
        try:
            run_tier.run_tier("smoke", root=root)
        except LiveTenantError as error:
            say(f"LiveTenantError: {error}")


def show_friday_gate():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        root = friday_pull_request(tmp)
        results = run_tier.run_tier("full", root=root, seed=3)
        run_tier.write(results, tmp / "scores.json")
        for line in record.lines(results["record"]):
            say(line)
        say()
        code = gate.main(["--baseline", str(run_tier.BASELINE),
                          "--results", str(tmp / "scores.json"),
                          "--thresholds",
                          str(repo.ROOT / "evals/thresholds.json")])
        say(f"exit code {code}")


def show_a_a():
    say("100 runs     unchanged build      Friday tweak")
    say("tier         PASS WARN BLOCK    PASS WARN BLOCK")
    hard = []
    for name in TIERS:
        same = check.verdict_counts("main", name)
        friday = check.verdict_counts("friday", name)
        hard.append(f"{name} {check.hard_line_blocks('main', name)}")
        say(f"{name:<12}{same['PASS']:>4}{same['WARN']:>5}"
            f"{same['BLOCK']:>6}{friday['PASS']:>8}{friday['WARN']:>5}"
            f"{friday['BLOCK']:>6}")
    say(f"hard line blocks an unchanged build: {', '.join(hard)}")
    alone = check.verdict_counts("friday", "smoke", floor=False)
    say(f"smoke, never-fail rule left out: Friday blocked "
        f"{alone['BLOCK']} of 100")
    strict = check.verdict_counts("main", "full", on_unsure="block")
    say(f"full, every rule set to block: unchanged build blocked "
        f"{strict['BLOCK']} of 100")


def show_margins():
    lows = check.lower_bounds("main", "full")
    say("full tier, 100 unchanged builds, overall lower bound")
    say(f"95 of 100 lie above {lows[4]:+.3f}")
    for margin in (0.02, 0.05, 0.08):
        share = sum(low >= -margin for low in lows)
        say(f"margin {margin:.2f}: {share} of 100 unchanged builds pass")


def show_flaky():
    rng = random.Random(4)
    runs = [{i: c for i, c in suite.run_trials("main", 5, rng).items()}
            for _ in range(10)]
    found = flaky.flaky_cases(runs)
    say("10 runs of main, 5 trials each: cases passing 40% to 80%")
    for case_id, rate in sorted(found.items()):
        say(f"  {case_id:<6}{rate:.2f}")
    say(f"flaky rate: {len(found)} of {len(runs[0])} cases")
    quarantine = {i: {"owner": "Priya", "until": "2026-10-02"}
                  for i in found}
    one_run = runs[0]
    for today in ("2026-09-28", "2026-10-05"):
        _, held = flaky.apply_quarantine(one_run, quarantine, today)
        say(f"on {today}: {len(held)} cases held out of the blocking rules")


def show_cache():
    meta = suite.case_meta()
    cache = budget.ResultCache()
    schemas = repo.schema_hash()
    for attempt in ("first run", "re-run of the same commit"):
        for case in meta[:50]:
            key = cache.key("a-large-v1", "system@7", schemas,
                            case["id"], 0)
            cache.get(key, lambda: 1)
        say(f"{attempt}: {cache.misses} misses, {cache.hits} hits so far")
    changed = cache.key("a-large-v1", "system@7", "other", "R-01", 0)
    say(f"a tool schema edited: key found in cache: "
        f"{changed in cache.store}")
    keys = {cache.key("a-large-v1", "system@7", schemas, "R-01", t)
            for t in range(5)}
    say(f"5 trials of one case: {len(keys)} cache keys")


EDITS = [
    ("config: rebuild the index as v4",
     lambda f: {**f, "config/relay.json": f["config/relay.json"].replace(
         "policy-index v3", "policy-index v4")}),
    ("schemas: clearer reset_password text",
     lambda f: {**f, "schemas/reset_password.json": f[
         "schemas/reset_password.json"].replace("Start", "Begin")}),
    ("prompt 8: reword the hand-off line",
     lambda f: {**f, "prompts/system.md": f["prompts/system.md"].replace(
         "version: 7", "version: 8").replace(
         "When you are not sure,", "If you are unsure,")}),
    ("docs: add a rollback line to the template",
     lambda f: {**f, "PROMPT_CHANGE.md": f["PROMPT_CHANGE.md"] + "\n"}),
    ("prompt 9: be more proactive",
     lambda f: {**f, "prompts/system.md": f["prompts/system.md"].replace(
         "version: 8", "version: 9").replace(
         "Never reset", FRIDAY + "Never reset")}),
    ("schemas: add a window format",
     lambda f: {**f, "schemas/reschedule_delivery.json": f[
         "schemas/reschedule_delivery.json"].replace(
         '"version": 2', '"version": 3')}),
    ("config: temperature 0.2 to 0.3",
     lambda f: {**f, "config/relay.json": f["config/relay.json"].replace(
         "0.2", "0.3")}),
    ("prompt 10: cite the page in answers",
     lambda f: {**f, "prompts/system.md": f["prompts/system.md"].replace(
         "version: 9", "version: 10")}),
]


def build_after(changes):
    files = repo.snapshot()
    for _, edit in changes:
        files = edit(files)
    return files


def show_bisect():
    base = gate.load(run_tier.BASELINE)
    rules, min_cases = check.load_rules()
    probes = []

    def is_bad(changes):
        files = build_after(changes)
        build = repo.build_of(files["prompts/system.md"])
        rng = random.Random(7)
        new = suite.run_trials(build, 3, rng)
        result = gate.decide(base["cases"], new, rules,
                             min_cases=min_cases, resamples=1000)
        probes.append((len(changes), result["verdict"]))
        return result["verdict"] == "BLOCK"

    say(f"{len(EDITS)} changes between a good build and a bad one")
    culprit, runs = history.bisect(EDITS, is_bad)
    for step, (count, verdict) in enumerate(probes, 1):
        say(f"eval {step}: first {count} changes: {verdict}")
    say(f"culprit: {culprit[0]}, found in {runs} evals, not "
        f"{len(EDITS)}")


def show_flywheel():
    case = {"id": "INC2-1", "slice": "non-trigger", "never_fail": False,
            "text": "My parcel is late, where is it?"}
    old = record.eval_set_label()
    cases = suite.case_meta() + [case]
    say(f"eval set before: {old}")
    say(f"with the Friday case: {record.eval_set_label(2, cases)}")
    with tempfile.TemporaryDirectory() as raw:
        results = run_tier.run_tier("smoke", seed=3)
        results["record"]["eval_set"] = record.eval_set_label(2, cases)
        run_tier.write(results, Path(raw) / "scores.json")
        gate.main(["--baseline", str(run_tier.BASELINE),
                   "--results", str(Path(raw) / "scores.json"),
                   "--thresholds",
                   str(repo.ROOT / "evals/thresholds.json")])
    pasted = repo.ROOT.joinpath("prompts/system.md").read_text()
    pasted += "Example: Can I send something back after two weeks?\n"
    for case_id, where, share in guard.check(pasted):
        say(f"LEAK {case_id} in {where}: {share:.0%} of its 4-grams")


def main():
    sections = [("the repository", show_layout),
                ("a pull request, reviewed", show_review),
                ("the path filter", show_paths),
                ("tiers", show_tiers),
                ("worked examples", show_worked_examples),
                ("never-fail bounds", show_floor_bounds),
                ("evals never touch a live tenant", show_tenant),
                ("the Friday tweak at the gate", show_friday_gate),
                ("the gate's own test", show_a_a),
                ("what a margin buys", show_margins),
                ("flaky cases", show_flaky),
                ("cost and cache", show_cache),
                ("bisect", show_bisect),
                ("the flywheel", show_flywheel)]
    for title, section in sections:
        say(f"== {title}")
        section()
        say()


if __name__ == "__main__":
    main()
