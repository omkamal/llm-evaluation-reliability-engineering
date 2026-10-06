"""A flaky Relay: Chapter 3's scripted answers, with sampling noise.

The stand-in in common/relay_fake.py gives the same answer every time,
which is handy for a first eval and unlike a real model. Here each case
gets a chance of passing on any one trial. These numbers are ILLUSTRATIVE:
they are a simulation, not a measurement of any real model.
"""
import random
from functools import lru_cache

from ch03_first_eval.run_evals import run
from ch04_numbers.stats import cluster_bootstrap_ci, paired_bootstrap

STAY_RIGHT = 0.94   # chance of passing when the scripted answer is right
LUCKY = 0.20        # chance of passing when the scripted answer is wrong


@lru_cache(maxsize=None)
def pass_chances(version):
    """Per-case chance of passing one trial, in the order of CASES."""
    return tuple(STAY_RIGHT if ok else LUCKY for _, ok, _ in run(version))


def one_run(version, rng):
    """One trial of every case: a list of 1 (pass) and 0 (fail)."""
    return [int(rng.random() < p) for p in pass_chances(version)]


def many_trials(version, trials, rng):
    """results[case][trial] for every case, `trials` trials each."""
    return [[int(rng.random() < p) for _ in range(trials)]
            for p in pass_chances(version)]


def case_scores(results):
    """Collapse the trials of each case into one score: its pass rate."""
    return [sum(trials) / len(trials) for trials in results]


def flagged_count(trials, repeats, seed=0):
    """Repeat the whole v1-versus-v2 experiment `repeats` times.

    Count the repeats in which the paired interval for v2 minus v1 sits
    entirely below zero: the repeats that would have flagged Friday.
    """
    rng = random.Random(seed)
    flagged = 0
    for _ in range(repeats):
        v1 = case_scores(many_trials("v1", trials, rng))
        v2 = case_scores(many_trials("v2", trials, rng))
        _, (_, upper) = paired_bootstrap(v1, v2, resamples=1_000)
        flagged += upper < 0
    return flagged


def false_alarm_count(trials, repeats, seed=0, clusters=None):
    """An A/A check, repeated: v1 against a second run of itself.

    Count the repeats in which the paired interval excludes zero, though
    nothing changed. A 95% interval promises about 5 in 100; a percentile
    bootstrap on thirty cases runs a little narrow and gives about 7, and
    on ten topics (pass `clusters`) narrower still, about 10.
    """
    rng = random.Random(seed)
    alarms = 0
    for _ in range(repeats):
        run_a = case_scores(many_trials("v1", trials, rng))
        run_b = case_scores(many_trials("v1", trials, rng))
        if clusters is None:
            _, (lo, hi) = paired_bootstrap(run_a, run_b, resamples=1_000)
        else:
            diffs = [b - a for a, b in zip(run_a, run_b)]
            _, (lo, hi) = cluster_bootstrap_ci(diffs, clusters,
                                               resamples=1_000)
        alarms += lo > 0 or hi < 0
    return alarms
