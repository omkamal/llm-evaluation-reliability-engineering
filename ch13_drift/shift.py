"""Did a distribution move? PSI, chi-square and Kolmogorov-Smirnov.

Three questions, three tools. PSI says how BIG a shift in a category mix
is. Chi-square says whether a shift in category counts could be chance.
Kolmogorov-Smirnov says whether two samples of a NUMBER with many
distinct values (length, latency) could come from one distribution; a
small count such as steps per task has too many ties for it.
PSI is one number for the whole mix, so it dilutes a big move in one
category: `tool_shares` gives each action tool its own rate band.
"""
from collections import Counter
from math import erfc, exp, lgamma, log, sqrt

from ch13_drift.bands import check_rate

FLOOR = 1e-4        # a share of exactly zero would make log() blow up


def shares(values, categories):
    """Each category's share of the values, floored so log() is safe."""
    counts = Counter(values)
    total = len(values)
    return [max(counts[c] / total, FLOOR) for c in categories]


def psi(base, now):
    """Population stability index between two lists of shares."""
    return sum((n - b) * log(n / b) for b, n in zip(base, now))


def psi_noise_floor(categories, n_base, n_now):
    """What PSI reads when NOTHING changed, on average: sampling noise."""
    return (categories - 1) * (1 / n_base + 1 / n_now)


def limits(categories, n_base, n_now, watch=0.10, shifted=0.25):
    """The usual 0.1 and 0.25, widened by this segment's own noise."""
    floor = psi_noise_floor(categories, n_base, n_now)
    return watch + floor, shifted + floor


def check_segment(base, now, categories, min_calls=500):
    """One segment: its PSI and a verdict, or a skip when data is thin."""
    if len(now) < min_calls:
        return None, f"skip: only {len(now)} calls"
    score = psi(shares(base, categories), shares(now, categories))
    watch, shifted = limits(len(categories), len(base), len(now))
    word = ("shifted" if score > shifted
            else "watch" if score > watch else "stable")
    return score, word


def tool_shares(base, now, tools):
    """Each tool's share of calls before and now, and a band verdict."""
    out = {}
    for tool in tools:
        before = base.count(tool) / len(base)
        out[tool] = (before, now.count(tool) / len(now),
                     check_rate(before, now.count(tool), len(now)))
    return out


def chi_square(base, now, categories):
    """Two-sample chi-square on category counts: (statistic, df)."""
    cb, cn = Counter(base), Counter(now)
    total = len(base) + len(now)
    stat, used = 0.0, 0
    for c in categories:
        col = cb[c] + cn[c]
        if col == 0:
            continue
        used += 1
        for seen, size in ((cb[c], len(base)), (cn[c], len(now))):
            expected = size * col / total
            stat += (seen - expected) ** 2 / expected
    return stat, used - 1


def chi2_sf(x, df):
    """Chance of a chi-square value this large if nothing changed."""
    q = erfc(sqrt(x / 2)) if df % 2 else exp(-x / 2)
    d = 1 if df % 2 else 2
    while d < df:           # each step up by two adds one exact term
        q += exp((d / 2) * log(x / 2) - x / 2 - lgamma(d / 2 + 1))
        d += 2
    return q


def ks_statistic(a, b):
    """Largest gap between the two samples' cumulative distributions."""
    a, b = sorted(a), sorted(b)
    i = j = 0
    gap = 0.0
    while i < len(a) and j < len(b):
        x = min(a[i], b[j])
        while i < len(a) and a[i] <= x:
            i += 1
        while j < len(b) and b[j] <= x:
            j += 1
        gap = max(gap, abs(i / len(a) - j / len(b)))
    return gap


def ks_p_value(gap, n_a, n_b):
    """Chance of a gap this big if both samples share one distribution."""
    ne = n_a * n_b / (n_a + n_b)
    lam = (sqrt(ne) + 0.12 + 0.11 / sqrt(ne)) * gap
    if lam < 0.2:           # the series needs many terms; p is above 0.99
        return 1.0
    total = sum((-1) ** (j - 1) * exp(-2 * j * j * lam * lam)
                for j in range(1, 101))
    return min(1.0, max(0.0, 2 * total))
