"""The eval report card: pass rates with intervals, and a paired gap.

Each list holds one score per case (a 0/1 verdict, or the pass rate over
that case's trials). The two lists must cover the same cases in the same
order, because the comparison is paired.

Each pass rate gets a Wilson interval with the CASES as n: right for 0/1
verdicts, a little wide for per-case rates, and never the zero-width
[1.00, 1.00] a bootstrap prints for 30 of 30. Pass `clusters` (one label
per case, such as its topic) when cases come in groups: the gap is then
also resampled group by group, and the verdict follows that interval.
"""
from ch04_numbers.stats import (cluster_bootstrap_ci, mean,
                                paired_bootstrap, wilson_ci)


def verdict(lo, hi):
    """Three honest answers, never two."""
    if hi < 0:
        return "worse: the whole interval is below zero"
    if lo > 0:
        return "better: the whole interval is above zero"
    return "inconclusive: zero is inside the interval"


def report_card(name_a, name_b, scores_a, scores_b, seed=0,
                clusters=None):
    """Return the lines of a report card for two versions."""
    if not all(0 <= s <= 1 for s in (*scores_a, *scores_b)):
        raise ValueError("the card takes pass rates from 0 to 1; use "
                         "paired_bootstrap for other scores")
    lines = []
    for name, scores in ((name_a, scores_a), (name_b, scores_b)):
        lo, hi = wilson_ci(sum(scores), len(scores))   # n = cases
        lines.append(f"{name}: pass rate {mean(scores):.2f}, "
                     f"95% CI [{lo:.2f}, {hi:.2f}]")
    gap, (lo, hi) = paired_bootstrap(scores_a, scores_b, seed=seed)
    lines.append(f"{name_b} minus {name_a}, paired: "
                 f"{gap:+.2f} [{lo:+.2f}, {hi:+.2f}]")
    if clusters is not None:
        diffs = [y - x for x, y in zip(scores_a, scores_b)]
        _, (lo, hi) = cluster_bootstrap_ci(diffs, clusters, seed=seed)
        lines.append(f"  by cluster: [{lo:+.2f}, {hi:+.2f}]")
    lines.append("verdict: " + verdict(lo, hi))
    return lines
