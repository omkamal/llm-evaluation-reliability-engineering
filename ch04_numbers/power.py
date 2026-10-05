"""How many cases do you need? One formula, two ways to fill it in.

To see a gap `delta` between two versions, at the 5% false-alarm level
and with an 80% chance of catching it when it is real:

    cases = Z ** 2 * V / delta ** 2

V is how much one case wobbles the gap. What goes in V is the whole
difference between comparing blindly and comparing on the same cases.
"""
from math import ceil, sqrt
from statistics import NormalDist

# 1.96 for the 95% interval, 0.84 for an 80% chance of catching a real gap
Z = NormalDist().inv_cdf(0.975) + NormalDist().inv_cdf(0.80)

# Miller (2024): variance of the per-question difference between two
# models in his worked example. For pass/fail cases it means roughly one
# case in nine changes its verdict between the two versions.
MILLER_VAR = 1 / 9


def independent_var(p):
    """V when the versions are scored separately, both near rate p."""
    return 2 * p * (1 - p)


def cases_needed(delta, var):
    """Cases per version needed to detect a gap of `delta`."""
    return ceil(Z ** 2 * var / delta ** 2)


def detectable_gap(n, var):
    """The smallest gap that n cases per version can reliably detect."""
    return Z * sqrt(var / n)
