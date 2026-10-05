"""How many cases: Miller's 969, the evaluation course's 200 and 800."""
from ch04_numbers.power import (MILLER_VAR, Z, cases_needed, detectable_gap,
                                independent_var)


def test_z_is_95_percent_confidence_plus_80_percent_power():
    assert round(Z, 3) == 2.802


def test_miller_three_point_gap_needs_969_questions():
    assert cases_needed(0.03, MILLER_VAR) == 969


def test_course_rule_of_thumb_from_85_percent():
    assert cases_needed(0.10, independent_var(0.85)) == 201   # "about 200"
    assert cases_needed(0.05, independent_var(0.85)) == 801   # "about 800"


def test_halving_the_gap_quadruples_the_cases():
    big = cases_needed(0.10, MILLER_VAR)
    small = cases_needed(0.05, MILLER_VAR)
    assert abs(small - 4 * big) <= 4


def test_pairing_needs_fewer_cases_than_scoring_separately():
    for points in (10, 5, 3, 2):
        gap = points / 100
        assert (cases_needed(gap, MILLER_VAR)
                < cases_needed(gap, independent_var(0.85)))


def test_detectable_gap_inverts_cases_needed():
    for n in (30, 200, 969):
        gap = detectable_gap(n, MILLER_VAR)
        assert cases_needed(gap, MILLER_VAR) in (n, n + 1)


def test_thirty_cases_cannot_see_two_points():
    assert round(detectable_gap(30, independent_var(0.85)), 2) == 0.26
    assert round(detectable_gap(30, MILLER_VAR), 2) == 0.17
    assert detectable_gap(30, MILLER_VAR) > 5 * 0.02


def test_variance_one_ninth_means_about_one_case_in_nine_flips():
    gap = 0.03
    flipping = MILLER_VAR + gap ** 2    # Var(d) = (share that flips) - gap^2
    assert round(flipping, 3) == 0.112
