"""The flaky Relay, the simulated A/B scores and the report card."""
import random

import pytest

from ch04_numbers.ab_scores import prompt_ab_scores
from ch04_numbers.noisy import (STAY_RIGHT, LUCKY, case_scores, flagged_count,
                                many_trials, one_run, pass_chances)
from ch04_numbers.report_card import report_card, verdict


def test_pass_chances_follow_the_scripted_answers():
    v1, v2 = pass_chances("v1"), pass_chances("v2")
    assert len(v1) == len(v2) == 30
    assert v1.count(LUCKY) == 2 and v2.count(LUCKY) == 7   # 28 and 23 right
    assert sum(1 for p in v1 if p == STAY_RIGHT) == 28


def test_one_run_is_reproducible_but_runs_differ():
    assert one_run("v1", random.Random(4)) == one_run("v1", random.Random(4))
    rng = random.Random(4)
    scores = [sum(one_run("v1", rng)) for _ in range(10)]
    assert len(set(scores)) > 3 and max(scores) - min(scores) >= 4


def test_a_threshold_of_28_fails_a_healthy_v1_most_of_the_time():
    rng = random.Random(9)
    met = sum(sum(one_run("v1", rng)) >= 28 for _ in range(4_000)) / 4_000
    assert 0.25 < met < 0.35
    met_v2 = sum(sum(one_run("v2", rng)) >= 28 for _ in range(4_000)) / 4_000
    assert met_v2 < 0.01


def test_trials_shape_and_case_scores():
    results = many_trials("v1", 5, random.Random(1))
    assert len(results) == 30 and all(len(t) == 5 for t in results)
    scores = case_scores([[1, 1, 0, 0], [1, 1, 1, 1]])
    assert scores == [0.5, 1.0]


def test_more_trials_per_case_flags_friday_more_often():
    one = flagged_count(1, 60)
    five = flagged_count(5, 60)
    assert five > one + 10


def test_ab_scores_are_whole_numbers_from_one_to_five():
    old, new = prompt_ab_scores()
    assert len(old) == len(new) == 200
    assert all(s in (1, 2, 3, 4, 5) for s in old + new)
    assert prompt_ab_scores() == (old, new)


def test_verdict_has_three_answers():
    assert verdict(-0.30, -0.03).startswith("worse")
    assert verdict(0.03, 0.21).startswith("better")
    assert verdict(-0.07, 0.31).startswith("inconclusive")
    assert verdict(-0.2, 0.0).startswith("inconclusive")   # touching zero
    assert verdict(0.0, 0.2).startswith("inconclusive")


def test_report_card_on_a_clear_regression_and_on_identical_runs():
    good = [1.0] * 20 + [0.8] * 10
    bad = [0.6] * 20 + [0.4] * 10
    lines = report_card("v1", "v2", good, bad)
    assert len(lines) == 4 and "worse" in lines[-1]
    same = report_card("v1", "v1 again", good, list(good))
    assert "+0.00 [+0.00, +0.00]" in same[2] and "inconclusive" in same[-1]


def test_report_card_refuses_mismatched_cases():
    with pytest.raises(ValueError):
        report_card("a", "b", [1, 0, 1], [1, 0])


def test_the_demo_prints_the_worked_examples(capsys):
    from ch04_numbers.demo import main
    main()
    out = capsys.readouterr().out
    for line in ("p = 0.75 per try, k = 3: pass@k 98.4%, pass^k 42.2%",
                 "paired:   +0.12 [+0.03, +0.21]",
                 "unpaired: +0.12 [-0.07, +0.31]"):
        assert line in out
