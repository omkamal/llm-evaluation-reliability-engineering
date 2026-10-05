"""PSI, chi-square and KS as tests. Reference values were computed once
with scipy 1.18 (in a throwaway environment), then written down here."""
import random
from math import log

import pytest

from ch13_drift.relay_sim import (BASE_MIX, SEGMENTS, TOOLS, input_chars,
                                  tool_calls)
from ch13_drift.shift import (check_segment, chi2_sf, chi_square,
                              ks_p_value, ks_statistic, limits, psi,
                              psi_noise_floor, shares)


def test_psi_by_hand():
    expected = 0.1 * log(0.6 / 0.5) + 0.1 * log(0.5 / 0.4)
    assert psi([0.5, 0.5], [0.6, 0.4]) == pytest.approx(expected)
    assert round(expected, 4) == 0.0405


def test_psi_is_zero_for_identical_and_symmetric():
    a, b = [0.5, 0.3, 0.2], [0.4, 0.4, 0.2]
    assert psi(a, a) == 0
    assert psi(a, b) == pytest.approx(psi(b, a))


def test_empty_category_does_not_break_the_log():
    base = ["a"] * 90 + ["b"] * 10
    now = ["a"] * 100                              # "b" vanished
    assert psi(shares(base, ["a", "b"]), shares(now, ["a", "b"])) > 0.25


def test_segment_psi_matches_figure_13_3():
    got = {}
    for seg in SEGMENTS:
        base, now = tool_calls(seg)
        score, word = check_segment(base, now, TOOLS)
        got[seg.name] = (round(score, 2), word)
    assert got == {"web chat": (0.04, "stable"),
                   "mobile chat": (0.07, "stable"),
                   "US email": (0.13, "watch"),
                   "EU chat": (0.18, "watch"),
                   "EU email": (0.31, "shifted")}


def test_thin_segments_are_skipped_and_limits_widen():
    base, now = tool_calls(SEGMENTS[0])
    score, word = check_segment(base, now[:140], TOOLS)
    assert score is None and word == "skip: only 140 calls"
    small = limits(5, 6000, 140)
    large = limits(5, 6000, 6000)
    assert small[0] > large[0] and small[1] > large[1]
    assert round(psi_noise_floor(5, 6000, 140), 3) == 0.029


def test_noise_floor_predicts_psi_when_nothing_changed():
    rng = random.Random(3)
    scores = []
    for _ in range(300):
        a = rng.choices(TOOLS, BASE_MIX, k=600)
        b = rng.choices(TOOLS, BASE_MIX, k=300)
        scores.append(psi(shares(a, TOOLS), shares(b, TOOLS)))
    floor = psi_noise_floor(5, 600, 300)
    assert sum(scores) / len(scores) == pytest.approx(floor, rel=0.15)


@pytest.mark.parametrize("x, df, p", [
    (3.841, 1, 0.05), (5.991, 2, 0.05), (9.488, 4, 0.05),
    (11.07, 5, 0.05), (1.0, 4, 0.9098)])
def test_chi2_sf_matches_reference(x, df, p):
    assert chi2_sf(x, df) == pytest.approx(p, abs=1e-3)


def test_chi_square_on_a_small_table():
    base = ["a"] * 50 + ["b"] * 30 + ["c"] * 20
    now = ["a"] * 30 + ["b"] * 40 + ["c"] * 30
    stat, df = chi_square(base, now, ["a", "b", "c"])
    assert stat == pytest.approx(8.4286, abs=1e-3) and df == 2
    assert chi2_sf(stat, df) == pytest.approx(0.01478, abs=1e-4)


def test_chi_square_is_psi_scaled_by_sample_size():
    for seg in SEGMENTS:
        base, now = tool_calls(seg)
        stat, _ = chi_square(base, now, TOOLS)
        scaled = psi(shares(base, TOOLS), shares(now, TOOLS)) / (
            1 / len(base) + 1 / len(now))
        assert stat == pytest.approx(scaled, rel=0.10)


def test_size_versus_chance():
    rng = random.Random(1)
    # huge n: a trivial shift is "significant" but PSI says stable
    a = rng.choices(TOOLS, BASE_MIX, k=200_000)
    b = rng.choices(TOOLS, (0.415, 0.303, 0.18, 0.03, 0.072), k=200_000)
    assert psi(shares(a, TOOLS), shares(b, TOOLS)) < 0.001
    assert chi2_sf(*chi_square(a, b, TOOLS)) < 0.001
    # tiny n: a big shift cannot be told from chance
    a = rng.choices(TOOLS, BASE_MIX, k=60)
    b = rng.choices(TOOLS, (0.22, 0.40, 0.15, 0.03, 0.20), k=60)
    assert psi(shares(a, TOOLS), shares(b, TOOLS)) > 0.1
    assert chi2_sf(*chi_square(a, b, TOOLS)) > 0.05


def test_ks_matches_reference():
    rng = random.Random(5)
    a = [rng.gauss(0, 1) for _ in range(300)]
    b = [rng.gauss(0.2, 1) for _ in range(200)]
    gap = ks_statistic(a, b)
    assert gap == pytest.approx(0.148333, abs=1e-5)
    assert 0.008 < ks_p_value(gap, 300, 200) < 0.0105   # exact 0.0094


def test_ks_edge_cases():
    x = [1.0, 2.0, 3.0]
    assert ks_statistic(x, x) == 0 and ks_p_value(0, 3, 3) == 1.0
    assert ks_statistic([1, 2, 3], [10, 11, 12]) == 1.0


def test_ks_sees_longer_emails_and_not_an_unchanged_week():
    rng = random.Random(8)
    before = input_chars(420, 6000, rng)
    same = input_chars(420, 1500, rng)
    longer = input_chars(560, 1500, rng)
    assert ks_p_value(ks_statistic(before, same), 6000, 1500) > 0.05
    assert ks_p_value(ks_statistic(before, longer), 6000, 1500) < 0.001
