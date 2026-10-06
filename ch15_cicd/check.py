"""The gate's own test: run a build through a tier many times.

Run an UNCHANGED build (an A/A check) and the gate should almost never
block it. Run the Friday tweak and it should block it most of the time.
Each run draws its own baseline of main: one committed baseline file
carries one draw's luck, and every count made against it shares that
luck. The numbers are simulated with Chapter 4's noise and are
illustrative.
"""
import json
import random
from collections import Counter

from ch04_numbers.stats import mean
from ch15_cicd import repo, suite
from ch15_cicd.gate import Rule, decide, overall
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


def pairs(build, tier_name, runs=100, seed=0, baseline=None):
    """`runs` pairs (main's baseline, a run of `build` at `tier_name`).
    Each baseline is a fresh full-strength run of main, unless one fixed
    `baseline` is given, as a committed file would be."""
    rng = random.Random(seed)
    for r in range(runs):
        base = baseline or one_run("main", "release", rng, sample_seed=r)
        yield base, one_run(build, tier_name, rng, sample_seed=r)


def verdict_counts(build, tier_name, runs=100, seed=0, resamples=300,
                   floor=True, on_unsure=None):
    """{PASS, WARN, BLOCK} counts over `runs` runs.

    With floor=False the never-fail rule is left out, to show what the
    intervals alone would have decided. `on_unsure` overrides every
    rule's setting (try "block")."""
    rules, min_cases = load_rules()
    if on_unsure:
        rules = [Rule(r.slice, r.margin, on_unsure) for r in rules]
    counts = Counter()
    for base, new in pairs(build, tier_name, runs, seed):
        result = decide(base, new, rules, min_cases=min_cases,
                        resamples=resamples)
        verdicts = [row["verdict"] for row in result["rows"]]
        if floor:
            verdicts.append(result["floor"]["verdict"])
        counts[overall(verdicts)] += 1
    return counts


def lower_bounds(build, tier_name, runs=100, seed=0, resamples=300):
    """Lower bound of the overall interval in each of `runs` runs."""
    rules, min_cases = load_rules()
    lows = []
    for base, new in pairs(build, tier_name, runs, seed):
        row = decide(base, new, rules, min_cases=min_cases,
                     resamples=resamples)["rows"][0]
        lows.append(round(row["lo"], 6))      # as the gate rounds it
    return sorted(lows)


def hard_line_blocks(build, tier_name, runs=100, seed=0, baseline=None):
    """Chapter 3's gate on the same runs: block if the score is below
    main's own score. Counts the blocks."""
    blocked = 0
    for base, new in pairs(build, tier_name, runs, seed, baseline):
        ids = sorted(new)
        before = mean([mean(base[i]["trials"]) for i in ids])
        after = mean([mean(new[i]["trials"]) for i in ids])
        blocked += after < before
    return blocked
