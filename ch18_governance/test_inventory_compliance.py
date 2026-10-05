"""Tests for the inventory, change control, control map and retention."""
from datetime import date

import pytest

from common.clock import FakeClock
from ch18_governance.audit import AuditLog
from ch18_governance.compliance import (CONTROLS, Control,
                                        criteria_evidenced, gaps,
                                        personal_data_found,
                                        retention_findings)
from ch18_governance.inventory import (Change, Item, apply_change,
                                       audit_inventory)

TODAY = date(2026, 10, 5)


def items():
    return [Item("prompt", "actioner", "v7", "sam", "2026-09-14"),
            Item("index", "policy-index", "2026-09", "", "2026-09-30"),
            Item("policy", "policy-sheet", "v3", "marcus", "2026-05-04")]


def test_inventory_audit_finds_unlisted_unowned_and_stale_items():
    running = {("prompt", "actioner", "v8"),
               ("index", "policy-index", "2026-09"),
               ("policy", "policy-sheet", "v3")}
    found = audit_inventory(items(), running, TODAY)
    assert "running, not listed: prompt actioner v8" in found
    assert "no owner: index policy-index" in found
    assert "unreviewed for 154 days: policy policy-sheet" in found


def good_change(**kw):
    base = dict(kind="prompt", name="actioner", new_version="v8",
                why="ask before any credit", author="sam",
                approver="priya", eval_run="run-0412")
    return Change(**{**base, **kw})


@pytest.mark.parametrize("edit, message", [
    ({"approver": "sam"}, "someone else"),
    ({"eval_run": ""}, "eval run"),
    ({"why": " "}, "reason"),
    ({"name": "nobody"}, "not listed"),
])
def test_a_change_without_its_conditions_is_refused(edit, message):
    log = AuditLog(FakeClock())
    with pytest.raises(ValueError, match=message):
        apply_change(items(), good_change(**edit), log, TODAY)
    assert log.events == []                   # a refusal leaves no change


def test_an_applied_change_updates_the_list_and_the_audit_log():
    log = AuditLog(FakeClock())
    out = apply_change(items(), good_change(), log, TODAY)
    assert out[0].version == "v8" and out[0].reviewed == "2026-10-05"
    assert log.events[0]["approver"] == "priya"
    assert log.events[0]["args"]["eval"] == "run-0412"


def test_the_control_map_has_no_wishes():
    assert gaps(CONTROLS) == []
    assert len(criteria_evidenced(CONTROLS)) == 16


def test_a_control_without_evidence_is_listed_as_a_wish():
    wish = Control("a policy nobody checks", 18, ("CC7.2",), ("MANAGE 4.1",),
                   "", "")
    assert gaps([wish]) == ["a policy nobody checks: no owner",
                            "a policy nobody checks: no evidence"]


def test_retention_findings_name_the_stores_over_their_limit():
    stores = [{"name": "trace_text", "oldest_days": 21},
              {"name": "audit_log", "oldest_days": 390}]
    policy = {"trace_text": 14, "audit_log": 400}
    assert retention_findings(stores, policy) == [
        "trace_text: oldest 21 days, policy 14"]


def test_the_redactor_still_misses_a_name_and_a_street():
    notes = ["Refund for ORD-004830, write to anna.k@example.test",
             "Supervisor said to call +49 30 1234567 about the credit",
             "Hannelore Vogt, Lindenstrasse 12, wants a goodwill credit"]
    assert personal_data_found(notes) == 2        # the third is unseen
