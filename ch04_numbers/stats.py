"""Small statistics for evals, standard library only.

Signatures of mean, pass_at_k, pass_hat_k, proportion_ci, difference_ci,
wilson_ci, bootstrap_ci, paired_bootstrap and sign_test_p are shared
with later chapters: keep them stable (add functions, never rename).
"""
import random
import statistics
from collections import defaultdict
from math import comb, sqrt


def mean(xs):
    return sum(xs) / len(xs)


# ---- repeated trials -------------------------------------------------

def check_k(n, k):
    """k draws from n trials need 1 <= k <= n: refuse, do not guess."""
    if not 1 <= k <= n:
        raise ValueError(f"k = {k} needs at least {k} trials, got {n}")


def pass_at_k(n, c, k):
    """Chance that at least one of k trials passes (n trials, c passes).

    Unbiased estimator from Chen et al. 2021.
    """
    check_k(n, k)
    if n - c < k:
        return 1.0      # fewer than k failures: any k draws hold a pass
    return 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n, c, k):
    """Chance that all k trials pass (n trials, c passes).

    Unbiased estimator from tau-bench (Yao et al. 2024).
    """
    check_k(n, k)
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

    The interval uses the normal approximation (the Wald interval):
    fine in the middle of the range with many cases, too narrow near 0
    or 1 and with few cases (zero width at 30 of 30). Use wilson_ci
    there; `coverage` measures the difference.
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
    """A better 95% interval near 0 or 1 (Wilson score interval).

    The default for a pass rate on few cases. `successes` may be a sum
    of per-case pass rates; the interval then errs on the wide side,
    because a rate over several trials wobbles less than one verdict.
    """
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    half /= 1 + z * z / n
    return max(0.0, centre - half), min(1.0, centre + half)


wilson_interval = wilson_ci     # the same function, by its longer name


def wilson_difference_ci(wins_a, n_a, wins_b, n_b, z=1.96):
    """Gap between two pass rates on separate samples, Wilson-based.

    Newcombe's (1998) method: combine each rate's Wilson interval. Use
    it in place of difference_ci when either rate is near 0 or 1 or
    either sample is small: 0 of 30 against 0 of 600 then still allows
    a harm of about 11 points, where difference_ci says (0.0, 0.0).
    Returns (rate_b - rate_a, (lo, hi)), like difference_ci.
    """
    pa, pb = wins_a / n_a, wins_b / n_b
    lo_a, hi_a = wilson_ci(wins_a, n_a, z)
    lo_b, hi_b = wilson_ci(wins_b, n_b, z)
    gap = pb - pa
    lo = gap - sqrt((pb - lo_b) ** 2 + (hi_a - pa) ** 2)
    hi = gap + sqrt((hi_b - pb) ** 2 + (pa - lo_a) ** 2)
    return gap, (lo, hi)


def coverage(interval, n, p):
    """Exact chance that `interval` contains the true rate p.

    `interval(successes, n)` returns (lo, hi). A 95% interval should
    score about 0.95; the Wald interval at 30 cases and p = 0.95 scores
    0.78. Every possible count of passes is weighed by its probability.
    """
    total = 0.0
    for wins in range(n + 1):
        lo, hi = interval(wins, n)
        if lo <= p <= hi:
            total += comb(n, wins) * p ** wins * (1 - p) ** (n - wins)
    return total


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


def cluster_bootstrap_ci(values, clusters, *, resamples=10_000,
                         alpha=0.05, seed=0):
    """Percentile bootstrap of the mean that resamples whole clusters.

    When cases come in groups (three phrasings of one topic), drawing
    single cases counts one piece of evidence three times. Here each
    draw takes a whole group, so ten topics are ten pieces of evidence.
    For a paired comparison, pass the per-case differences b - a. With
    few clusters it runs narrow: on ten topics an A/A check flags a
    difference about 10 times in 100, not 5.
    """
    if len(values) != len(clusters):
        raise ValueError(f"{len(values)} scores but {len(clusters)} "
                         "cluster labels: give one label per case")
    groups = defaultdict(list)
    for value, cluster in zip(values, clusters):
        groups[cluster].append(value)
    groups = list(groups.values())
    rng = random.Random(seed)
    g = len(groups)
    stats = sorted(
        mean([v for _ in range(g) for v in groups[rng.randrange(g)]])
        for _ in range(resamples))
    lo = stats[int(resamples * alpha / 2)]
    hi = stats[int(resamples * (1 - alpha / 2)) - 1]
    return mean(values), (lo, hi)


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

    The p-value is the chance of a split at least this lopsided, in
    either direction, if the versions were equally good. Cases that did
    not change carry no information and are left out. With few changed
    cases (under about twenty), trust it over the paired bootstrap.
    """
    changed = better + worse
    rarer = min(better, worse)
    tail = sum(comb(changed, i) for i in range(rarer + 1)) / 2 ** changed
    return min(1.0, 2 * tail)
