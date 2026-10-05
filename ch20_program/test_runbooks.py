"""Tests for the runbook freshness check."""
from datetime import date

from ch20_program import relay_data as rd
from ch20_program.runbooks import Runbook, audit, problems

TODAY = date(2026, 10, 5)


def book(**kw):
    base = dict(name="b", author="Ana", lines=20,
                last_drilled="2026-09-01", drilled_by="Bo")
    return Runbook(**{**base, **kw})


def test_a_sound_runbook_has_no_problems():
    assert problems(book(), TODAY) == []


def test_each_way_a_runbook_goes_bad():
    assert problems(book(lines=31), TODAY) == [
        "31 lines (one screen is 30)"]
    assert problems(book(last_drilled="", drilled_by=""), TODAY) == [
        "never drilled"]
    assert problems(book(drilled_by="Ana"), TODAY) == [
        "drilled only by its author"]
    assert problems(book(last_drilled="2026-05-14"), TODAY) == [
        "not drilled for 144 days"]


def test_ninety_days_is_fine_ninety_one_is_stale():
    assert problems(book(last_drilled="2026-07-07"), TODAY) == []
    assert problems(book(last_drilled="2026-07-06"), TODAY) == [
        "not drilled for 91 days"]


def test_the_audit_matches_the_text():
    found, sound, total = audit(rd.PAGE_ALERTS, rd.RUNBOOKS, TODAY)
    assert (sound, total) == (1, 4)
    assert found == [
        "BudgetBurnFast: provider failover: not drilled for 144 days",
        "BudgetBurnMedium: provider-failover-old does not exist",
        "RefundShareUp: refund share: 52 lines (one screen is 30)",
        "RefundShareUp: refund share: drilled only by its author"]


def test_an_alert_with_no_link_is_reported():
    found, sound, total = audit({"A": ""}, [], TODAY)
    assert found == ["A: no runbook linked"] and (sound, total) == (0, 1)


def test_the_failover_runbook_was_last_drilled_at_the_game_day():
    # the game day finding (Chapter 20) is the same date
    failover = next(b for b in rd.RUNBOOKS if b.name == "provider failover")
    assert failover.last_drilled == "2026-05-14"
