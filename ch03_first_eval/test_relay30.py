"""Relay-30 as a pytest gate. `pytest -q ch03_first_eval`"""
from ch03_first_eval.cases import CASES
from ch03_first_eval.run_evals import grade, run

BASELINE = 28          # what the current Relay (v1) scores today; a drop below this blocks the change


def test_every_case_has_pass_criteria_written_down():
    assert len(CASES) == 30
    assert len({c["id"] for c in CASES}) == 30
    assert all(c["must_contain"] for c in CASES)


def test_grader_is_strict_but_not_brittle():
    case = {"must_contain": [r"14 days"], "must_not_contain": ["reschedul"]}
    assert grade(case, "Returns are accepted within 14 days of delivery.")[0]
    assert not grade(case, "Within 30 days.")[0]
    assert not grade(case, "14 days. Shall I reschedule your delivery?")[0]


def test_current_relay_meets_the_baseline():
    assert sum(ok for _, ok, _ in run("v1")) >= BASELINE


def test_the_friday_tweak_is_caught():
    passed = sum(ok for _, ok, _ in run("v2"))
    assert passed < BASELINE, "the gate should have blocked this change"
