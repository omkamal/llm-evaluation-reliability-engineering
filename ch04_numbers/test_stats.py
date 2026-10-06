"""Chapter 4 statistics: every worked example in the text is asserted."""
import random
import statistics
from math import sqrt

import pytest

from ch03_first_eval.cases import CASES
from ch03_first_eval.run_evals import run
from ch04_numbers.ab_scores import prompt_ab_scores
from ch04_numbers.stats import (bootstrap_ci, cluster_bootstrap_ci,
                                clustered_se, coverage, difference_ci,
                                mean, paired_bootstrap, paired_vs_unpaired_se,
                                pass_at_k, pass_at_k_rate, pass_hat_k,
                                pass_hat_k_rate, proportion_ci, sign_test_p,
                                unpaired_bootstrap, wilson_ci,
                                wilson_difference_ci, wilson_interval)

TOPICS = [case["topic"] for case in CASES]


def verdicts(version):
    return [int(ok) for _, ok, _ in run(version)]


# ---- pass@k and pass^k ----------------------------------------------

def test_worked_example_75_percent_per_try():
    assert round(pass_at_k_rate(0.75, 3), 3) == 0.984
    assert round(pass_hat_k_rate(0.75, 3), 3) == 0.422
    assert round(pass_hat_k_rate(0.75, 8), 2) == 0.10


def test_unbiased_estimators_on_ten_trials_seven_passes():
    assert round(pass_at_k(10, 7, 3), 3) == 0.992
    assert round(pass_hat_k(10, 7, 3), 3) == 0.292


def test_plug_in_formulas_are_biased_in_opposite_directions():
    assert round(pass_at_k_rate(0.7, 3), 3) == 0.973   # too low
    assert round(pass_hat_k_rate(0.7, 3), 3) == 0.343  # too high
    assert pass_at_k_rate(0.7, 3) < pass_at_k(10, 7, 3)
    assert pass_hat_k_rate(0.7, 3) > pass_hat_k(10, 7, 3)


def test_estimators_agree_at_k_equals_one_and_with_the_formula_for_big_n():
    assert pass_at_k(10, 7, 1) == pass_hat_k(10, 7, 1) == 0.7
    assert abs(pass_at_k(10_000, 7_500, 3) - 0.984375) < 0.001
    assert abs(pass_hat_k(10_000, 7_500, 3) - 0.421875) < 0.001


def test_edges_and_ordering():
    assert pass_at_k(10, 8, 3) == 1.0        # only 2 failures: a pass is certain
    assert pass_hat_k(10, 2, 3) == 0.0       # fewer than 3 passes
    for c in range(11):
        for k in (1, 2, 3, 5):
            assert pass_hat_k(10, c, k) <= pass_at_k(10, c, k) + 1e-12


def test_estimators_refuse_more_draws_than_trials():
    # pass@10 from 5 trials used to come back as 1.0 for a case that
    # never passed; pass^5 of 5 out of 10 used to divide by zero
    for bad in ((5, 0, 10), (3, 0, 5), (5, 5, 10), (10, 3, 0)):
        with pytest.raises(ValueError):
            pass_at_k(*bad)
        with pytest.raises(ValueError):
            pass_hat_k(*bad)
    assert pass_at_k(5, 0, 5) == 0.0 and pass_hat_k(5, 5, 5) == 1.0


# ---- standard error and intervals -----------------------------------

def test_forty_of_fifty():
    p, se, (lo, hi) = proportion_ci(40, 50)
    assert round(p, 2) == 0.80 and round(se, 3) == 0.057
    assert round(1.96 * se, 2) == 0.11
    assert (round(lo, 2), round(hi, 2)) == (0.69, 0.91)


def test_four_times_the_cases_halves_the_error():
    se_50 = proportion_ci(40, 50)[1]
    se_200 = proportion_ci(160, 200)[1]
    assert se_200 == pytest.approx(se_50 / 2)


def test_relay_30_intervals_overlap():
    _, _, (lo1, hi1) = proportion_ci(28, 30)
    _, _, (lo2, hi2) = proportion_ci(23, 30)
    assert (round(lo1, 2), round(lo2, 2), round(hi2, 2)) == (0.84, 0.62, 0.92)
    assert hi1 > 1.0               # the normal interval spills past 100%
    assert lo1 < hi2               # and the two intervals overlap


def test_wilson_stays_inside_zero_to_one():
    lo, hi = wilson_ci(28, 30)
    assert (round(lo, 2), round(hi, 2)) == (0.79, 0.98)
    for wins in (0, 30):
        lo, hi = wilson_ci(wins, 30)
        assert 0.0 <= lo <= hi <= 1.0
    assert wilson_interval is wilson_ci


def wald(wins, n):
    return proportion_ci(wins, n)[2]


def test_the_chapter_prints_wilson_for_sams_numbers():
    pairs = [tuple(round(x, 2) for x in wilson_ci(w, 30))
             for w in (28, 23, 30, 24)]
    assert pairs == [(0.79, 0.98), (0.59, 0.88), (0.89, 1.0), (0.63, 0.9)]
    lo1, _ = wilson_ci(28, 30)
    _, hi2 = wilson_ci(23, 30)
    assert lo1 < hi2                       # Sam's intervals still overlap


def test_the_formula_fails_with_few_cases_near_the_top():
    assert wald(30, 30) == (1.0, 1.0)      # zero width: false certainty
    assert round(wald(28, 30)[1], 2) == 1.02
    # how often each interval contains the true rate, 30 cases
    assert round(coverage(wald, 30, 0.95), 2) == 0.78
    assert round(coverage(wald, 30, 0.93), 2) == 0.88
    assert round(coverage(wilson_ci, 30, 0.95), 2) == 0.94
    for p in (0.80, 0.90, 0.93, 0.95, 0.98):
        assert coverage(wilson_ci, 30, p) > 0.93
    # in the middle of the range, with 50 cases, the formula is fine
    assert coverage(wald, 50, 0.80) > 0.93


def test_wilson_difference_keeps_width_where_the_formula_collapses():
    gap, (lo, hi) = difference_ci(0, 600, 0, 30)
    assert (lo, hi) == (0.0, 0.0)          # "no possible harm": false
    gap, (lo, hi) = wilson_difference_ci(0, 600, 0, 30)
    assert gap == 0 and lo < 0 and round(hi, 3) == 0.114
    gap, (lo, hi) = wilson_difference_ci(28, 30, 23, 30)
    assert (round(lo, 2), round(hi, 2)) == (-0.35, 0.02)
    # with many cases in the middle it agrees with the formula
    _, (wlo, whi) = wilson_difference_ci(400, 500, 440, 500)
    _, (flo, fhi) = difference_ci(400, 500, 440, 500)
    assert abs(wlo - flo) < 0.005 and abs(whi - fhi) < 0.005


def test_overlap_is_a_conservative_test():
    # figure 3 (illustrative): the intervals overlap and so does zero
    gap, (lo, hi) = difference_ci(40, 50, 44, 50)
    assert round(gap, 2) == 0.08 and lo < 0 < hi
    # 35 versus 44: the intervals still overlap, yet the gap is real
    _, _, (_, hi_a) = proportion_ci(35, 50)
    _, _, (lo_b, _) = proportion_ci(44, 50)
    gap, (lo, hi) = difference_ci(35, 50, 44, 50)
    assert hi_a > lo_b and 0 < lo
    assert (round(lo, 2), round(hi, 2)) == (0.02, 0.34)


# ---- clusters --------------------------------------------------------

def test_clusters_of_identical_cases_inflate_the_error_by_root_m():
    values = [1, 1, 1, 0, 0, 0] * 5            # ten topics, three copies
    clusters = [i // 3 for i in range(30)]
    naive = proportion_ci(sum(values), 30)[1]
    ratio = clustered_se(values, clusters) / naive
    assert 1.6 < ratio < 1.9                    # about sqrt(3)


def test_relay_30_clusters_matter_for_v2_but_not_v1():
    topics = [case["topic"] for case in CASES]
    ratios = {}
    for version in ("v1", "v2"):
        scores = verdicts(version)
        naive = proportion_ci(sum(scores), 30)[1]
        ratios[version] = clustered_se(scores, topics) / naive
    assert round(ratios["v1"], 1) == 1.0 and round(ratios["v2"], 1) == 1.7
    assert round(clustered_se(verdicts("v2"), topics), 3) == 0.132


def test_cluster_bootstrap_counts_topics_not_rows():
    v1, v2 = verdicts("v1"), verdicts("v2")
    diffs = [b - a for a, b in zip(v1, v2)]
    changed = {TOPICS[i] for i, d in enumerate(diffs) if d}
    assert changed == {"returns", "windows"}    # five cases, two topics
    gap, (lo, hi) = cluster_bootstrap_ci(diffs, TOPICS)
    assert round(gap, 2) == -0.17
    assert (round(lo, 2), round(hi, 2)) == (-0.40, 0.0)
    assert hi == 0                  # by topic, Friday is not proven
    with pytest.raises(ValueError):
        cluster_bootstrap_ci(diffs, TOPICS[:-1])


def test_cluster_bootstrap_with_one_case_per_cluster_is_the_bootstrap():
    values = [1] * 24 + [0] * 6
    assert (cluster_bootstrap_ci(values, list(range(30)), seed=3)
            == bootstrap_ci(values, seed=3))


# ---- the bootstrap ----------------------------------------------------

def test_figure_four_bootstrap_numbers():
    sample = [1] * 24 + [0] * 6
    rng = random.Random(11)
    rng.shuffle(sample)
    means = [mean([sample[rng.randrange(30)] for _ in range(30)])
             for _ in range(3)]
    assert [round(m, 2) for m in means] == [0.77, 0.83, 0.80]
    rate, (lo, hi) = bootstrap_ci(sample, seed=11)
    assert rate == 0.8 and (round(lo, 2), round(hi, 2)) == (0.63, 0.93)
    wlo, whi = wilson_ci(24, 30)                 # a few hundredths away
    assert (round(wlo, 2), round(whi, 2)) == (0.63, 0.90)


def test_the_bootstrap_fails_like_the_formula_at_thirty_of_thirty():
    assert bootstrap_ci([1] * 30)[1] == (1.0, 1.0)
    assert round(wilson_ci(30, 30)[0], 2) == 0.89


def test_bootstrap_is_reproducible_and_takes_any_statistic():
    scores = [1, 2, 2, 3, 4, 4, 4, 5, 5, 5]
    a = bootstrap_ci(scores, resamples=500, seed=3, stat=statistics.median)
    b = bootstrap_ci(scores, resamples=500, seed=3, stat=statistics.median)
    assert a == b and a[1][0] <= a[0] <= a[1][1]


def test_bootstrap_agrees_with_the_formula_for_a_mean():
    values = [1] * 160 + [0] * 40
    _, (lo, hi) = bootstrap_ci(values, resamples=4_000)
    _, _, (nlo, nhi) = proportion_ci(160, 200)
    assert abs(lo - nlo) < 0.01 and abs(hi - nhi) < 0.01


# ---- pairing ------------------------------------------------------------

def test_variance_of_a_difference_identity_and_the_thirty_percent():
    a, b = prompt_ab_scores()
    var_diff = statistics.variance([y - x for x, y in zip(a, b)])
    identity = (statistics.variance(a) + statistics.variance(b)
                - 2 * statistics.covariance(a, b))
    assert var_diff == pytest.approx(identity)
    assert round(1 - sqrt(1 - 0.5), 2) == 0.29


def test_pairing_shrinks_the_error_when_correlation_is_one_half():
    rng = random.Random(5)
    a = [rng.gauss(0, 1) for _ in range(20_000)]
    b = [0.5 * x + sqrt(0.75) * rng.gauss(0, 1) for x in a]   # rho = 0.5
    paired, unpaired, rho = paired_vs_unpaired_se(a, b)
    assert rho == pytest.approx(0.5, abs=0.02)
    assert paired / unpaired == pytest.approx(sqrt(0.5), abs=0.02)


def test_prompt_ab_example_paired_versus_unpaired():
    old, new = prompt_ab_scores()
    gap, (lo, hi) = paired_bootstrap(old, new)
    assert round(gap, 2) == 0.12
    assert (round(lo, 2), round(hi, 2)) == (0.03, 0.21)
    _, (ulo, uhi) = unpaired_bootstrap(old, new)
    assert (round(ulo, 2), round(uhi, 2)) == (-0.07, 0.31)
    assert ulo < 0 < lo                 # pairing turns a shrug into a call


def test_pairing_wins_for_other_seeds_not_just_the_chosen_one():
    for seed in range(30):
        old, new = prompt_ab_scores(seed=seed)
        paired, unpaired, rho = paired_vs_unpaired_se(old, new)
        assert rho > 0.6 and paired < 0.7 * unpaired


def test_paired_comparison_refuses_mismatched_lists():
    with pytest.raises(ValueError):
        paired_bootstrap([1, 0, 1], [1, 0])
    with pytest.raises(ValueError):
        paired_vs_unpaired_se([1.0, 2.0, 3.0], [1.0, 2.0])


def test_friday_on_relay_30():
    v1, v2 = verdicts("v1"), verdicts("v2")
    assert (sum(v1), sum(v2)) == (28, 23)
    diffs = [b - a for a, b in zip(v1, v2)]
    assert (diffs.count(1), diffs.count(-1), diffs.count(0)) == (0, 5, 25)
    gap, (lo, hi) = difference_ci(28, 30, 23, 30)
    assert round(gap, 2) == -0.17 and (round(lo, 2), round(hi, 2)) == (-0.34, 0.01)
    gap, (lo, hi) = paired_bootstrap(v1, v2)
    assert (round(lo, 2), round(hi, 2)) == (-0.30, -0.03)
    # the chapter prints the Wilson-based gap for 30 cases
    _, (lo, hi) = wilson_difference_ci(28, 30, 23, 30)
    assert lo < 0 < hi


def test_sign_test():
    assert sign_test_p(5, 0) == 0.0625
    assert sign_test_p(0, 5) == 0.0625
    assert sign_test_p(3, 3) == 1.0 and sign_test_p(0, 0) == 1.0
    assert round(sign_test_p(9, 1), 4) == 0.0215


def test_twenty_slices_and_one_false_alarm():
    assert round(1 - 0.95 ** 20, 2) == 0.64


def test_shuffling_breaks_the_pairing_exercise_three():
    old, new = prompt_ab_scores()
    random.Random(1).shuffle(new)
    gap, (lo, hi) = paired_bootstrap(old, new)
    assert round(gap, 2) == 0.12
    assert (round(lo, 2), round(hi, 2)) == (-0.07, 0.30)


def test_overlap_of_independent_intervals_means_the_gap_excludes_zero():
    # no overlap implies the gap's own interval excludes zero (z = 1.96)
    for wins_a in range(5, 46):
        for wins_b in range(5, 46):
            _, _, (lo_a, hi_a) = proportion_ci(wins_a, 50)
            _, _, (lo_b, hi_b) = proportion_ci(wins_b, 50)
            if hi_a < lo_b:
                _, (lo, _) = difference_ci(wins_a, 50, wins_b, 50)
                assert lo > 0
