"""Pins the shared agreement code to the worked example in the book's figure (200 labels)."""
from ch05_judge.agreement import (chance_agreement, cohen_kappa, confusion,
                                  landis_koch, observed_agreement, tpr_tnr)

JUDGE = ["pass"] * 190 + ["fail"] * 10
# 175 + 15 judge-pass, 5 + 5 judge-fail:  expert says (pass, fail, pass, fail)
EXPERT = (["pass"] * 175 + ["fail"] * 15) + (["pass"] * 5 + ["fail"] * 5)


def test_the_kappa_worked_example():
    assert confusion(JUDGE, EXPERT) == (175, 15, 5, 5)
    assert observed_agreement(JUDGE, EXPERT) == 0.90
    assert round(chance_agreement(JUDGE, EXPERT), 3) == 0.86
    assert round(cohen_kappa(JUDGE, EXPERT), 2) == 0.29
    assert landis_koch(cohen_kappa(JUDGE, EXPERT)) == "fair"


def test_a_judge_that_always_passes_looks_good_and_is_not():
    expert = ["pass"] * 90 + ["fail"] * 10
    always = ["pass"] * 100
    assert observed_agreement(always, expert) == 0.90
    assert cohen_kappa(always, expert) == 0.0
    assert tpr_tnr(always, expert) == (1.0, 0.0)
