"""The eval report card: pass rates with intervals, and a paired gap.

Each list holds one score per case (a 0/1 verdict, or the pass rate over
that case's trials). The two lists must cover the same cases in the same
order, because the comparison is paired.
"""
from ch04_numbers.stats import bootstrap_ci, paired_bootstrap


def verdict(lo, hi):
    """Three honest answers, never two."""
    if hi < 0:
        return "worse: the whole interval is below zero"
    if lo > 0:
        return "better: the whole interval is above zero"
    return "inconclusive: zero is inside the interval"


def report_card(name_a, name_b, scores_a, scores_b, seed=0):
    """Return the lines of a report card for two versions."""
    lines = []
    for name, scores in ((name_a, scores_a), (name_b, scores_b)):
        rate, (lo, hi) = bootstrap_ci(scores, seed=seed)
        lines.append(
            f"{name}: pass rate {rate:.2f}, 95% CI [{lo:.2f}, {hi:.2f}]")
    gap, (lo, hi) = paired_bootstrap(scores_a, scores_b, seed=seed)
    lines.append(f"{name_b} minus {name_a}, paired: "
                 f"{gap:+.2f} [{lo:+.2f}, {hi:+.2f}]")
    lines.append("verdict: " + verdict(lo, hi))
    return lines
