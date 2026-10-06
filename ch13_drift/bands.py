"""Baseline bands: what a metric normally does, per segment.

A band is a range of expected values. A value outside it is worth a look;
the same value inside it is noise. The width starts from Chapter 4's
standard error, never from a number someone picked. At high volume,
weekdays and traffic mix move a metric more than sampling luck does, so
`segment_band` widens it to the spread of the segment's own past windows.
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


def noise_band(runs, z=2.0, floor=0.0):
    """Band from repeated runs of an unchanged setup (an A/A check).

    `floor` is the narrowest half-width allowed: one case of a probe set,
    so a probe that never varies (stdev 0) does not flag on one case.
    """
    centre, spread = mean(runs), stdev(runs)
    half = max(z * spread, floor)
    return centre - half, centre + half


def segment_band(past, se, z=2.0):
    """Band from a segment's own past windows: z times whichever is
    wider, the sampling error `se` or how far past windows really moved
    (weekdays and traffic mix move them more than luck does)."""
    half = z * max(se, stdev(past))
    return mean(past) - half, mean(past) + half


def false_alarm_rate(p, n, windows, k, runs=10_000, seed=0):
    """Share of clean runs where a drop rule still alerts (simulated).

    Only windows BELOW the band count, as in the chapter's decay alerts;
    a window above the band is good news, not an alarm.
    """
    rng = random.Random(seed)
    lo, _ = rate_band(p, n)
    se = sqrt(p * (1 - p) / n)
    alarms = 0
    for _ in range(runs):
        flags = [rng.gauss(p, se) < lo for _ in range(windows)]
        alarms += first_alert(flags, k) is not None
    return alarms / runs
