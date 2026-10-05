"""Baseline bands: what a metric normally does, per segment.

A band is a range of expected values. A value outside it is worth a look;
the same value inside it is noise. The width comes from Chapter 4's
standard error, never from a number someone picked.
"""
import random
from math import sqrt
from statistics import mean, stdev


def rate_band(p, n, z=2.0):
    """Where a rate of p should land when measured on n answers."""
    se = sqrt(p * (1 - p) / n)
    return p - z * se, p + z * se


def mean_band(centre, sd, n, z=2.0):
    """The same idea for an average (steps per task) with spread sd."""
    se = sd / sqrt(n)
    return centre - z * se, centre + z * se


def check_rate(base_p, good, n, min_n=50, z=2.0):
    """One segment, one window: skip, inside, below or above its band."""
    if n < min_n:
        return f"skip: only {n} answers"
    lo, hi = rate_band(base_p, n, z)
    rate = good / n
    return "below" if rate < lo else "above" if rate > hi else "inside"


def first_alert(flags, k=2):
    """Index where the k-th flag in a row arrives, or None."""
    run = 0
    for i, flag in enumerate(flags):
        run = run + 1 if flag else 0
        if run == k:
            return i
    return None


def noise_band(runs, z=2.0):
    """Band from repeated runs of an unchanged setup (an A/A check)."""
    centre, spread = mean(runs), stdev(runs)
    return centre - z * spread, centre + z * spread


def false_alarm_rate(p, n, windows, k, runs=1000, seed=0):
    """Share of clean runs that still raise an alert (simulated)."""
    rng = random.Random(seed)
    lo, hi = rate_band(p, n)
    se = sqrt(p * (1 - p) / n)
    alarms = 0
    for _ in range(runs):
        flags = [not lo <= rng.gauss(p, se) <= hi for _ in range(windows)]
        alarms += first_alert(flags, k) is not None
    return alarms / runs
