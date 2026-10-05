"""Chapter 13 bands, as tests.   pytest -q ch13_drift"""
import random
from datetime import date

import pytest

from ch13_drift.bands import (check_rate, false_alarm_rate, first_alert,
                              mean_band, noise_band, rate_band)
from ch13_drift.online import judged_by_segment
from ch13_drift.relay_sim import SEGMENTS, weekly_decay, week_of_conversations


def test_standard_error_examples_from_the_chapter():
    lo, hi = rate_band(0.8, 100)                  # SE 0.04: +/- 8 points
    assert (round(lo, 3), round(hi, 3)) == (0.72, 0.88)
    lo, hi = rate_band(0.8, 2500)                 # SE 0.008
    assert (round(lo, 3), round(hi, 3)) == (0.784, 0.816)


def test_band_matches_the_figure_recipe():
    lo, hi = rate_band(0.91, 1000)                # Figure 13.2's band
    assert (round(100 * lo, 2), round(100 * hi, 2)) == (89.19, 92.81)


def test_four_times_the_answers_halves_the_band():
    w100 = rate_band(0.8, 100)
    w400 = rate_band(0.8, 400)
    assert (w100[1] - w100[0]) == pytest.approx(2 * (w400[1] - w400[0]))


def test_mean_band():
    lo, hi = mean_band(4.0, 1.6, 30000)
    assert (hi - lo) / 2 == pytest.approx(2 * 1.6 / 30000 ** 0.5)


def test_check_rate_four_answers():
    assert check_rate(0.8, 30, 30).startswith("skip")      # too thin
    assert check_rate(0.8, 80, 100) == "inside"
    assert check_rate(0.8, 60, 100) == "below"
    assert check_rate(0.8, 95, 100) == "above"
    assert check_rate(0.8, 80, 100, min_n=200).startswith("skip")


def test_first_alert_needs_flags_in_a_row():
    assert first_alert([False, True, False, True, True], 2) == 4
    assert first_alert([True, False, True, False], 2) is None
    assert first_alert([True], 1) == 0
    assert first_alert([], 2) is None


def test_persistence_cuts_false_alarms():
    one = false_alarm_rate(0.91, 1000, 16, 1)
    two = false_alarm_rate(0.91, 1000, 16, 2)
    assert 0.40 < one < 0.60          # about half of clean runs cry wolf
    assert two < 0.06                 # two in a row almost never does
    assert false_alarm_rate(0.91, 1000, 16, 1) == one      # seeded


def test_noise_band_is_mean_plus_minus_two_sd():
    lo, hi = noise_band([0.9, 0.92, 0.94, 0.9, 0.94])
    assert (lo + hi) / 2 == pytest.approx(0.92)
    assert hi - lo == pytest.approx(4 * 0.02, rel=0.2)


def test_weekly_decay_leaves_the_band_in_week_11():
    rates = weekly_decay(34)               # the run the chapter prints
    lo, hi = rate_band(0.91, 1000)
    outside = [i + 1 for i, r in enumerate(rates) if not lo <= r <= hi]
    assert outside[0] == 11
    assert first_alert([r < lo for r in rates], 2) + 1 == 12


def test_online_sample_feeds_the_band_and_the_queue():
    counts, queue = judged_by_segment(week_of_conversations(2))
    judged = sum(n for n, _ in counts.values())
    assert judged == 1015                       # about 5% of 20,000
    failed = judged - sum(g for _, g in counts.values())
    assert len(queue) == failed                 # every failure is queued
    assert queue[0][1].startswith("C-")         # a trace id, not text
    verdict = {s.name: check_rate(s.base_good, counts[s.name][1],
                                  counts[s.name][0]) for s in SEGMENTS}
    assert verdict.pop("EU email") == "below"
    assert set(verdict.values()) == {"inside"}


def test_a_global_number_can_hide_a_sick_segment():
    counts, _ = judged_by_segment(week_of_conversations(2))
    total = sum(n for n, _ in counts.values())
    good = sum(g for _, g in counts.values())
    base = sum(s.share * s.base_good for s in SEGMENTS)
    assert check_rate(base, good, total) == "inside"        # all fine?
    n, g = counts["EU email"]
    assert check_rate(0.80, g, n) == "below"                # no it is not
    assert date(2026, 10, 4) > date(2026, 1, 1)             # (dates sane)


def test_clean_week_has_no_alert_in_the_segment_table():
    rng = random.Random(0)
    n, p = 400, 0.93
    flags = [not rate_band(p, n)[0] <= rng.gauss(p, (p * (1 - p) / n)
                                                 ** 0.5) <= rate_band(p, n)[1]
             for _ in range(8)]
    assert first_alert(flags, 2) is None
