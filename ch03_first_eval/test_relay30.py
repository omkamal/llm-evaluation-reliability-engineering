"""Relay-30 as a pytest gate. `pytest -q ch03_first_eval`"""
import pathlib
import types

import common.relay_fake as relay_fake
from ch03_first_eval.cases import CASES, case
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


def test_run_keeps_every_answer_so_failures_can_be_read():
    answers = {}
    results = run("v1", answers=answers)
    assert set(answers) == {c["id"] for c in CASES}
    assert [cid for cid, ok, _ in results if not ok] == ["R-02", "R-06"]
    assert answers["R-02"] == relay_fake.FALLBACK          # handed off
    assert "14 days" in answers["R-06"]                    # return, not refund
    v2 = {}
    run("v2", answers=v2)
    assert "30 days" in v2["R-01"] and "reschedule" in v2["R-13"]


def relay_copy(old, new):
    """A private copy of the stand-in with one edit, as exercise 1 asks."""
    source = pathlib.Path(relay_fake.__file__).read_text()
    assert source.count(old) == 1
    module = types.ModuleType("my_relay")
    exec(source.replace(old, new), module.__dict__)
    return module


def test_exercise_1_works_on_a_copy_and_leaves_the_shared_file_alone():
    my_relay = relay_copy(
        '("returns", ["return"],',
        '("returns", ["return", "send something back", "send it back"],')
    results = run("v1", ask=my_relay.ask)
    assert sum(ok for _, ok, _ in results) == 29
    assert [cid for cid, ok, _ in results if not ok] == ["R-06"]
    assert sum(ok for _, ok, _ in run("v1")) == BASELINE   # original intact
    # exercise 3: a phrasing the fix never saw still falls through
    jacket = "Can I bring back a jacket I bought last week?"
    assert my_relay.ask(jacket, "v1") == my_relay.FALLBACK


def test_exercise_2_a_second_window_needs_its_own_rule():
    r31 = case("R-31", "returns", "What is your return policy?",
               [r"14 days"], [r"30 days"])
    r03 = next(c for c in CASES if c["id"] == "R-03")
    assert [ok for _, ok, _ in run("v1", [r31])] == [True]
    assert [ok for _, ok, _ in run("v2", [r31, r03])] == [False, False]
    both = "Returns are accepted within 14 days, or 30 days for sale items."
    assert grade(r03, both) == (True, "ok")                # R-03 misses it
    assert grade(r31, both) == (False, "volunteered /30 days/")
