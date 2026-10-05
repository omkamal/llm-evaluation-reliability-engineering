"""The gate's own test: run a build through a tier many times.

Run an UNCHANGED build (an A/A check) and the gate should almost never
block it. Run the Friday tweak and it should block it most of the time.
The numbers are simulated with Chapter 4's noise and are illustrative.
"""
import json
import random
from collections import Counter

from ch04_numbers.stats import mean
from ch15_cicd import repo, suite
from ch15_cicd.gate import ORDER, Rule, decide
from ch15_cicd.run_tier import BASELINE
from ch15_cicd.tiers import TIERS, pick_sample


def load_rules(path=repo.ROOT / "evals" / "thresholds.json"):
    cfg = json.loads(path.read_text())
    return [Rule(**r) for r in cfg["rules"]], cfg["min_cases"]


def one_run(build, tier_name, rng, sample_seed):
    tier = TIERS[tier_name]
    meta = suite.case_meta()
    never = {c["id"] for c in meta if c["never_fail"]}
    ids = pick_sample([c["id"] for c in meta], never, tier.sample,
                      sample_seed)
    return suite.run_trials(build, tier.trials, rng, set(ids),
                            tier.safety_trials)


def verdict_counts(build, tier_name, runs=100, seed=0, resamples=300,
                   floor=True, on_unsure=None):
    """{PASS, WARN, BLOCK} counts over `runs` runs against main.

    With floor=False the never-fail rule is left out, to show what the
    intervals alone would have decided. `on_unsure` overrides every
    rule's setting (try "block")."""
    base = json.loads(BASELINE.read_text())["cases"]
    rules, min_cases = load_rules()
    if on_unsure:
        rules = [Rule(r.slice, r.margin, on_unsure) for r in rules]
    rng = random.Random(seed)
    counts = Counter()
    for r in range(runs):
        new = one_run(build, tier_name, rng, sample_seed=r)
        result = decide(base, new, rules, min_cases=min_cases,
                        resamples=resamples)
        rows = [row["verdict"] for row in result["rows"]]
        verdicts = rows + ([result["floor"]["verdict"]] if floor else [])
        counts[max(verdicts, key=ORDER.get)] += 1
    return counts


def lower_bounds(build, tier_name, runs=100, seed=0, resamples=300):
    """Lower bound of the overall interval in each of `runs` runs."""
    base = json.loads(BASELINE.read_text())["cases"]
    rules, min_cases = load_rules()
    rng = random.Random(seed)
    lows = []
    for r in range(runs):
        new = one_run(build, tier_name, rng, sample_seed=r)
        row = decide(base, new, rules, min_cases=min_cases,
                     resamples=resamples)["rows"][0]
        lows.append(row["lo"])
    return sorted(lows)


def hard_line_blocks(build, tier_name, runs=100, seed=0):
    """Chapter 3's gate on the same runs: block if the score is below
    main's own score. Counts the blocks."""
    base = json.loads(BASELINE.read_text())["cases"]
    rng = random.Random(seed)
    blocked = 0
    for r in range(runs):
        new = one_run(build, tier_name, rng, sample_seed=r)
        ids = sorted(new)
        before = mean([mean(base[i]["trials"]) for i in ids])
        after = mean([mean(new[i]["trials"]) for i in ids])
        blocked += after < before
    return blocked
