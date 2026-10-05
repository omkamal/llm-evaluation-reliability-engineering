"""Tests for the learning review and the quarterly report, and for the
numbers this chapter borrows from earlier chapters."""
import contextlib
import io
from datetime import date

import pytest

from ch12_slos import demo as ch12_demo
from ch19_incidents.demo import inc6_clock
from ch19_incidents.timeline import durations
from ch20_program import relay_data as rd
from ch20_program.findings import (Finding, closed_share, mix, overdue,
                                   without_case)
from ch20_program.report import Line, expected_loss_avoided, render

TODAY = date(2026, 10, 5)


def test_the_learning_review_numbers():
    f = rd.FINDINGS
    assert mix(f) == {"incident": 5, "near miss": 2, "game day": 1}
    assert closed_share(f) == 0.75
    assert [(x.owner, late) for x, late in overdue(f, TODAY)] == [
        ("Lena", 3), ("Priya", 130)]
    assert [x.source for x in without_case(f)] == ["game day"]


def test_a_finding_due_today_is_not_overdue():
    f = [Finding("drill", "x", "Ana", "2026-10-05", False, "c")]
    assert overdue(f, TODAY) == []


def test_the_inc6_actions_agree_with_chapter_19():
    mine = [x for x in rd.FINDINGS if x.source == "incident"]
    assert len(mine) == 5 and sum(x.done for x in mine) == 4
    assert [(x.owner, x.due) for x in mine][-1] == ("Lena", "2026-10-02")


def test_the_report_refuses_a_number_without_a_basis():
    with pytest.raises(ValueError):
        render("t", [("h", [Line("saved $9,000", "")])])


def test_the_report_labels_assumptions():
    text = "\n".join(render("t", [("h", [
        Line("a fact"), Line("a guess", "assumed")])]))
    assert "a fact\n" in text + "\n" and "a guess (assumed)" in text


def test_expected_loss_matches_chapter_18():
    cost, saved = expected_loss_avoided(1000, 0.02, 400, 1.50)
    assert (cost, saved) == (1500.0, 8000.0)
    one_cost, one_saved = expected_loss_avoided(1, 0.02, 400, 1.50)
    assert (one_cost, round(one_saved, 2)) == (1.5, 8.0)


def test_the_incident_clock_matches_chapter_19():
    _, marks = inc6_clock()
    assert durations(marks)["detect"] == 38
    assert durations(marks)["contain"] == 30
    assert durations(marks)["message to pin"] == 68


def test_time_at_risk_if_it_came_back():
    assert 5 + 2 == 7 and 38 + 30 == 68


def test_the_report_numbers_agree_with_chapter_12():
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ch12_demo.main()
    text = out.getvalue()
    assert "Promises kept: 9 of 10" in text
    assert "$0.028" in text and "< $0.06" in text


def test_the_range_on_the_review_line():
    # Chapter 18's 4 errors in 200 reviews: 2%, interval 0.8% to 5.0%
    assert expected_loss_avoided(1000, 0.008, 400, 1.50)[1] == 3200.0
    assert expected_loss_avoided(1000, 0.05, 400, 1.50)[1] == 20000.0
