"""How many cases do you need? One formula, two ways to fill it in.

To see a gap `delta` between two versions with a 95% two-sided interval
(a 5% false-alarm rate when nothing changed) and an 80% chance of
catching the gap when it is real (80% power):

    cases = Z ** 2 * V / delta ** 2

V is how much one case wobbles the gap. What goes in V is the whole
difference between comparing blindly and comparing on the same cases.
The cases must be independent: trials of one case do not count.
"""
from math import ceil, sqrt
from statistics import NormalDist

# 1.96 for the 95% interval, 0.84 for an 80% chance of catching a real gap
Z = NormalDist().inv_cdf(0.975) + NormalDist().inv_cdf(0.80)

# 1.96 alone: the gap's interval just reaches zero, so a real gap of
# exactly delta is caught only half the time (50% power).
Z_INTERVAL_ONLY = NormalDist().inv_cdf(0.975)

# Miller (2024): variance of the per-question difference between two
# models in his worked example. For pass/fail cases it means roughly one
# case in nine changes its verdict between the two versions.
MILLER_VAR = 1 / 9


def independent_var(p, p2=None):
    """V when the versions are scored separately, at rates p and p2.

    With p2 left out both versions sit at p: the common rule of thumb,
    which undercounts when the second version is lower (nearer 50%).
    """
    p2 = p if p2 is None else p2
    return p * (1 - p) + p2 * (1 - p2)


def cases_needed(delta, var, z=Z):
    """Independent cases per version needed to detect a gap of `delta`."""
    return ceil(z ** 2 * var / delta ** 2)


def detectable_gap(n, var, z=Z):
    """The smallest gap that n cases per version can reliably detect."""
    return z * sqrt(var / n)


def detectable_drop(n, p):
    """The smallest drop from rate p that n cases scored separately see.

    The lower rate sets part of V, so solve for it a few times over.
    """
    drop = detectable_gap(n, independent_var(p))
    for _ in range(50):
        drop = detectable_gap(n, independent_var(p, p - drop))
    return drop
