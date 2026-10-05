"""Small statistics for evals, standard library only.

Signatures of mean, pass_at_k, pass_hat_k, proportion_ci, bootstrap_ci
and paired_bootstrap are shared with later chapters: keep them stable.
"""
import random
import statistics
from collections import defaultdict
from math import comb, sqrt


def mean(xs):
    return sum(xs) / len(xs)


# ---- repeated trials -------------------------------------------------

def pass_at_k(n, c, k):
    """Chance that at least one of k trials passes (n trials, c passes).

    Unbiased estimator from Chen et al. 2021.
    """
    if n - c < k:
        return 1.0      # fewer than k failures: any k draws hold a pass
    return 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n, c, k):
    """Chance that all k trials pass (n trials, c passes)."""
    return comb(c, k) / comb(n, k)


def pass_at_k_rate(p, k):
    """Same question when the per-try success rate p is known."""
    return 1 - (1 - p) ** k


def pass_hat_k_rate(p, k):
    """Chance that k tries in a row all succeed, given rate p."""
    return p ** k


# ---- one score, with an error bar -----------------------------------

def proportion_ci(successes, n, z=1.96):
    """Pass rate, its standard error, and a 95% interval.

    The interval uses the normal approximation: fine in the middle of
    the range, optimistic near 0 or 1 and with few cases.
    """
    p = successes / n
    se = sqrt(p * (1 - p) / n)
    return p, se, (p - z * se, p + z * se)


def difference_ci(wins_a, n_a, wins_b, n_b, z=1.96):
    """Gap between two pass rates measured on separate samples.

    Returns (rate_b - rate_a, (lo, hi)). Variances add, because the
    two measurements are treated as unrelated.
    """
    pa, pb = wins_a / n_a, wins_b / n_b
    se = sqrt(pa * (1 - pa) / n_a + pb * (1 - pb) / n_b)
    return pb - pa, (pb - pa - z * se, pb - pa + z * se)


def wilson_ci(successes, n, z=1.96):
    """A better 95% interval near 0 or 1 (Wilson score interval)."""
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    half /= 1 + z * z / n
    return max(0.0, centre - half), min(1.0, centre + half)


def clustered_se(values, clusters):
    """Standard error of the mean when cases come in clusters.

    Cases in a cluster (three phrasings of one question) are not three
    independent pieces of evidence, so the unit of evidence is the
    cluster. G / (G - 1) is the usual small-sample correction.
    """
    n = len(values)
    centre = mean(values)
    spread = defaultdict(float)
    for value, cluster in zip(values, clusters):
        spread[cluster] += value - centre
    g = len(spread)
    total = sum(s * s for s in spread.values())
    return sqrt(g / (g - 1) * total) / n


# ---- the bootstrap ---------------------------------------------------

def bootstrap_ci(values, *, resamples=10_000, alpha=0.05, seed=0,
                 stat=mean):
    """Percentile bootstrap interval for any statistic of the scores."""
    rng = random.Random(seed)
    n = len(values)
    stats = sorted(stat([values[rng.randrange(n)] for _ in range(n)])
                   for _ in range(resamples))
    lo = stats[int(resamples * alpha / 2)]
    hi = stats[int(resamples * (1 - alpha / 2)) - 1]
    return stat(values), (lo, hi)


def check_same_cases(a, b):
    """Fail loudly: zip() would quietly drop the extra scores."""
    if len(a) != len(b):
        raise ValueError(f"{len(a)} scores against {len(b)}: a paired "
                         "comparison needs the same cases in both lists")


def paired_bootstrap(a, b, **kw):
    """Interval for the mean of the per-case differences b - a.

    Both lists score the SAME cases, in the same order. We resample the
    differences, so each case keeps its two scores together.
    """
    check_same_cases(a, b)
    return bootstrap_ci([y - x for x, y in zip(a, b)], **kw)


def unpaired_bootstrap(a, b, *, resamples=10_000, alpha=0.05, seed=0):
    """Interval for mean(b) - mean(a), resampling each list on its own.

    This is what you get if you forget the two lists share their cases.
    """
    rng = random.Random(seed)
    na, nb = len(a), len(b)    # unpaired: the lists may differ in length
    gaps = sorted(
        mean([b[rng.randrange(nb)] for _ in range(nb)])
        - mean([a[rng.randrange(na)] for _ in range(na)])
        for _ in range(resamples))
    lo = gaps[int(resamples * alpha / 2)]
    hi = gaps[int(resamples * (1 - alpha / 2)) - 1]
    return mean(b) - mean(a), (lo, hi)


def paired_vs_unpaired_se(a, b):
    """Standard error of mean(b) - mean(a) both ways, and correlation.

    Unpaired: Var(A) + Var(B). Paired: Var(A) + Var(B) - 2 Cov(A, B).
    """
    check_same_cases(a, b)
    n = len(a)
    var_a, var_b = statistics.variance(a), statistics.variance(b)
    unpaired = sqrt(var_a / n + var_b / n)
    paired = statistics.stdev([y - x for x, y in zip(a, b)]) / sqrt(n)
    return paired, unpaired, statistics.correlation(a, b)


def sign_test_p(better, worse):
    """Exact two-sided p-value if each changed case is a fair coin flip.

    Cases that did not change carry no information and are left out.
    """
    changed = better + worse
    rarer = min(better, worse)
    tail = sum(comb(changed, i) for i in range(rarer + 1)) / 2 ** changed
    return min(1.0, 2 * tail)
