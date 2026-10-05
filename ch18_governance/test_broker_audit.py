"""Tests for the credential broker, the door and the audit trail."""
import pytest

from ch06_agents.sandbox import call_tool, new_state, ord_id
from common.clock import FakeClock
from ch18_governance.audit import AuditLog
from ch18_governance.broker import (CAPS_CENTS, GRANTS, Broker,
                                    NeedsApproval, NotGranted, Refused)
from ch18_governance.door import Door, Payments

MONEY = {"issue_refund"}


def setup():
    clock = FakeClock()
    broker, log, pay = Broker(clock), AuditLog(clock), Payments()
    door = Door(broker, log, {"issue_refund": pay.issue_refund})
    return clock, broker, log, pay, door


def test_only_the_actioner_may_hold_money_tools():
    for agent, tools in GRANTS.items():
        assert bool(tools & MONEY) == (agent == "actioner")


def test_a_hijacked_researcher_cannot_get_a_refund_key():
    _, broker, *_ = setup()
    with pytest.raises(NotGranted):
        broker.issue("researcher", "issue_refund", "t1", "cust-31")
    with pytest.raises(NotGranted):
        broker.issue("summarizer", "lookup_order", "t1", "cust-31")


def test_the_default_token_is_capped_at_the_auto_limit():
    _, broker, *_ = setup()
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    assert token.max_cents == CAPS_CENTS["issue_refund"] == 5_000


def test_over_the_cap_needs_a_person_and_an_agent_is_not_one():
    _, broker, *_ = setup()
    with pytest.raises(NeedsApproval):
        broker.issue("actioner", "issue_refund", "t1", "cust-31",
                     max_cents=40_000)
    with pytest.raises(NeedsApproval):
        broker.issue("actioner", "issue_refund", "t1", "cust-31",
                     max_cents=40_000, approver="planner")
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31",
                         max_cents=40_000, approver="reviewer-7")
    assert token.approver == "reviewer-7"


@pytest.mark.parametrize("tool, customer, cents, code", [
    ("issue_refund", "cust-31", 40_000, "over_cap"),
    ("issue_refund", "cust-44", 2_000, "wrong_customer"),
    ("create_ticket", "cust-31", 0, "wrong_tool"),
])
def test_a_token_refuses_what_is_out_of_scope(tool, customer, cents, code):
    _, broker, *_ = setup()
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    with pytest.raises(Refused) as err:
        broker.check(token, tool, customer, cents)
    assert err.value.code == code


def test_a_token_expires_after_fifteen_minutes_exactly():
    clock, broker, *_ = setup()
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    clock.sleep(899)
    broker.check(token, "issue_refund", "cust-31", 2_000)    # still fine
    clock.sleep(1)
    with pytest.raises(Refused) as err:
        broker.check(token, "issue_refund", "cust-31", 2_000)
    assert err.value.code == "expired"


def test_a_money_token_is_single_use_and_a_read_token_is_not():
    _, broker, *_ = setup()
    pay = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    broker.spend(pay)
    with pytest.raises(Refused) as err:
        broker.check(pay, "issue_refund", "cust-31", 100)
    assert err.value.code == "unknown_or_used"
    read = broker.issue("researcher", "lookup_order", "t1", "cust-31",
                        uses=3)
    for _ in range(3):
        broker.check(read, "lookup_order", "cust-31")
        broker.spend(read)


def test_the_door_runs_the_tool_and_records_who_and_what():
    _, broker, log, pay, door = setup()
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    args = {"order_id": "ORD-004830", "amount_cents": 2_000}
    door.call(token, "issue_refund", args, "cust-31", "trace-1")
    assert pay.ledger == [("issue_refund", "ORD-004830")]
    event = log.events[0]
    assert (event["agent"], event["decision"], event["trace"]) == (
        "actioner", "allow", "trace-1")
    with pytest.raises(Refused):                       # a second use
        door.call(token, "issue_refund", args, "cust-31", "trace-1")
    assert log.events[1]["decision"] == "deny:unknown_or_used"
    assert len(pay.ledger) == 1


def test_a_denied_call_never_reaches_the_payments_service():
    _, broker, log, pay, door = setup()
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    with pytest.raises(Refused):
        door.call(token, "issue_refund",
                  {"order_id": "ORD-004830", "amount_cents": 40_000},
                  "cust-31", "trace-1")
    assert pay.ledger == []
    assert log.events[0]["decision"] == "deny:over_cap"


def test_chapter_6_kept_two_fields_and_the_record_keeps_more():
    state = new_state(0)
    call_tool(state, "reschedule_delivery", order_id=ord_id(0),
              window="Thu 10:00-12:00")
    assert set(state["audit_log"][0]) == {"tool", "target"}
    log = AuditLog(FakeClock())
    event = log.record(agent="actioner", version="v7", tool="x", args={},
                       decision="allow", trace="t", task="k")
    assert {"agent", "version", "decision", "approver", "trace",
            "prev", "hash"} <= set(event)


def test_editing_an_old_record_breaks_the_chain_at_that_record():
    clock = FakeClock()
    log = AuditLog(clock)
    for k in range(4):
        log.record(agent="actioner", version="v7", tool="issue_refund",
                   args={"order_id": f"ORD-00483{k}", "amount_cents": 2_000},
                   decision="allow", trace="t", task=f"k{k}")
    assert log.verify() is None
    log.events[1]["args"]["amount_cents"] = 100
    assert log.verify() == 1


def test_deleting_a_record_is_also_visible():
    log = AuditLog(FakeClock())
    for k in range(3):
        log.record(agent="a", version="v", tool="t", args={},
                   decision="allow", trace="t", task=str(k))
    del log.events[1]
    assert log.verify() == 1


def test_coverage_counts_changes_that_have_no_record():
    clock, broker, log, pay, door = setup()
    for k in range(4):
        token = broker.issue("actioner", "issue_refund", f"t{k}", "cust-31")
        door.call(token, "issue_refund",
                  {"order_id": f"ORD-0048{30 + k}", "amount_cents": 2_000},
                  "cust-31", "trace-1")
    assert log.coverage(pay.ledger) == 1.0
    pay.issue_refund("ORD-004899", 2_500)           # bypasses the door
    assert log.coverage(pay.ledger) == pytest.approx(0.8)
    assert log.coverage([]) == 1.0


def test_dropping_the_last_record_is_not_visible_to_the_chain_alone():
    log = AuditLog(FakeClock())
    for k in range(4):
        log.record(agent="a", version="v", tool="t",
                   args={"order_id": f"O{k}"}, decision="allow",
                   trace="t", task="k")
    log.events.pop()                      # the tail goes quietly
    assert log.verify() is None           # keep the newest hash elsewhere
