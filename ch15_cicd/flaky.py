"""Flaky cases: the ones that flip on a build that did not change."""
from ch04_numbers.stats import mean


def pooled_rates(runs):
    """Pass rate of each case over every trial of every run."""
    rates = {}
    for case_id in runs[0]:
        trials = [t for run in runs for t in run[case_id]["trials"]]
        rates[case_id] = mean(trials)
    return rates


def flaky_cases(runs, low=0.4, high=0.8):
    """Cases of one unchanged build that neither pass nor fail steadily.

    `runs` are repeated runs of the SAME build. A case that passes about
    half the time is the case's problem or the grader's, not the build's.
    """
    rates = pooled_rates(runs)
    return {i: r for i, r in rates.items() if low < r < high}


def apply_quarantine(results, quarantine, today):
    """Drop quarantined cases from the blocking rules, until they expire.

    Returns (kept, held). An entry past its date is not honoured: a
    quarantine is a loan, not a pardon.
    """
    held = {i for i, q in quarantine.items() if q["until"] >= today}
    kept = {i: c for i, c in results.items() if i not in held}
    return kept, sorted(held & set(results))
