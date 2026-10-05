"""Pins the shared statistics to the worked examples used in the book's figures."""
from ch04_numbers.stats import (bootstrap_ci, mean, paired_bootstrap,
                                pass_at_k, pass_hat_k, proportion_ci)


def test_pass_at_k_and_pass_hat_k_worked_example():
    # p = 0.75 per try, k = 3: the estimators with n = 4, c = 3 and the closed forms agree
    assert round(1 - (1 - 0.75) ** 3, 3) == 0.984 and round(0.75 ** 3, 3) == 0.422
    assert pass_at_k(4, 3, 1) == 0.75 and pass_hat_k(4, 3, 1) == 0.75


def test_forty_of_fifty():
    p, se, (lo, hi) = proportion_ci(40, 50)
    assert round(p, 2) == 0.80 and round(1.96 * se, 2) == 0.11
    assert (round(lo, 2), round(hi, 2)) == (0.69, 0.91)


def test_bootstrap_is_reproducible_and_brackets_the_mean():
    scores = [1] * 24 + [0] * 6
    m, (lo, hi) = bootstrap_ci(scores, seed=11)
    assert m == 0.8 and lo < m < hi
    assert bootstrap_ci(scores, seed=11) == (m, (lo, hi))


def test_paired_difference():
    a, b = [0, 0, 1, 1, 0, 1], [1, 0, 1, 1, 1, 1]
    m, (lo, hi) = paired_bootstrap(a, b, seed=3)
    assert round(m, 3) == round(mean([y - x for x, y in zip(a, b)]), 3)
