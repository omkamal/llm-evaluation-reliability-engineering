"""The flaky Relay, the simulated A/B scores and the report card."""
import random
import statistics

import pytest

from ch04_numbers.ab_scores import prompt_ab_scores
from ch03_first_eval.cases import CASES
from ch04_numbers.noisy import (STAY_RIGHT, LUCKY, case_scores,
                                false_alarm_count, flagged_count,
                                many_trials, one_run, pass_chances)
from ch04_numbers.report_card import report_card, verdict
from ch04_numbers.stats import proportion_ci

TOPICS = [case["topic"] for case in CASES]


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
    with pytest.raises(ValueError):          # rubric scores are not rates
        report_card("a", "b", [4, 5, 3], [5, 5, 4])


def test_report_card_never_claims_certainty_from_thirty_of_thirty():
    lines = report_card("a", "b", [1] * 30, [1] * 30)
    assert lines[0] == "a: pass rate 1.00, 95% CI [0.89, 1.00]"
    lines = report_card("a", "b", [1] * 29 + [0], [1] * 30)
    assert lines[0] == "a: pass rate 0.97, 95% CI [0.83, 0.99]"


def test_report_card_by_topic_on_friday_at_five_trials():
    rng = random.Random(0)
    v1 = case_scores(many_trials("v1", 5, rng))
    v2 = case_scores(many_trials("v2", 5, rng))
    plain = report_card("v1", "v2", v1, v2)
    assert plain[2] == "v2 minus v1, paired: -0.12 [-0.25, -0.01]"
    assert plain[-1].startswith("verdict: worse")   # counted by case
    lines = report_card("v1", "v2", v1, v2, clusters=TOPICS)
    assert lines[0] == "v1: pass rate 0.89, 95% CI [0.73, 0.96]"
    assert lines[3] == "  by cluster: [-0.32, +0.03]"
    assert "inconclusive" in lines[-1]              # counted by topic


def test_a_a_false_alarms_run_near_seven_in_a_hundred():
    # Python 3.12 gives 18, 78 and 39; other versions' random streams differ
    # by a few counts, so the tests assert the band the chapter describes
    assert 10 <= false_alarm_count(5, 400) <= 26          # 4.5% here: a lucky seed
    assert 65 <= false_alarm_count(5, 1_000, seed=1) <= 90   # about 7 in 100
    # ten topics are few units: the cluster interval runs narrower still
    assert 30 <= false_alarm_count(5, 400, clusters=TOPICS) <= 50   # about 10


def test_ten_trials_of_thirty_cases_are_not_three_hundred_cases():
    assert round(proportion_ci(0.89 * 300, 300)[1], 3) == 0.018
    assert round(proportion_ci(0.89 * 30, 30)[1], 3) == 0.057
    for seed in range(3):
        rates = case_scores(many_trials("v1", 10, random.Random(seed)))
        honest = statistics.stdev(rates) / 30 ** 0.5
        assert 0.035 < honest < 0.045           # "about 0.04"


def test_the_demo_prints_the_worked_examples(capsys):
    from ch04_numbers.demo import main
    main()
    out = capsys.readouterr().out
    for line in ("p = 0.75 per try, k = 3: pass@k 98.4%, pass^k 42.2%",
                 "paired:   +0.12 [+0.03, +0.21]",
                 "unpaired: +0.12 [-0.07, +0.31]",
                 "by topic: -0.17 [-0.40, +0.00]",
                 "10 pts       248      88"):
        assert line in out
