"""Tests for the credential broker, the door and the audit trail."""
import dataclasses
from datetime import date

import pytest

from ch02_trust_outputs.refund import Order
from ch06_agents.sandbox import call_tool, new_state, ord_id
from common.clock import FakeClock
from ch18_governance.audit import AuditLog, Sealer
from ch18_governance.broker import (CAPS_CENTS, GRANTS, Broker,
                                    NeedsApproval, NotGranted, Refused)
from ch18_governance.door import Door, Payments, Refunds

MONEY = {"issue_refund"}
TODAY = date(2026, 10, 5)


def setup():
    clock = FakeClock()
    orders = {f"ORD-0048{30 + k}": Order("cust-31", 52_000)
              for k in range(4)}
    orders["ORD-007777"] = Order("cust-44", 9_900)     # a stranger's
    broker, log, pay = Broker(clock), AuditLog(clock), Payments()
    refunds = Refunds(pay, orders, today=lambda: TODAY)
    door = Door(broker, log, {"issue_refund": refunds})
    return clock, broker, log, pay, door


def refund(door, token, order="ORD-004830", cents=2_000,
           session="cust-31"):
    return door.call(token, "issue_refund",
                     {"order_id": order, "amount_cents": cents}, session,
                     "trace-1")


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


@pytest.mark.parametrize("approver", ["human", "manager", "Reviewer-7",
                                      "", "reviewer-7 "])
def test_a_string_that_is_not_a_known_reviewer_never_lifts_the_cap(
        approver):
    _, broker, *_ = setup()
    with pytest.raises(NeedsApproval):
        broker.issue("actioner", "issue_refund", "t1", "cust-31",
                     max_cents=10_000_000, approver=approver)


def test_a_token_copied_with_a_wider_scope_is_refused():
    _, broker, *_ = setup()
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    wider = dataclasses.replace(token, max_cents=40_000, customer="cust-44",
                                expires_at=1e18)
    with pytest.raises(Refused) as err:
        broker.check(wider, "issue_refund", "cust-44", 40_000)
    assert err.value.code == "unknown_or_used"


@pytest.mark.parametrize("tool, customer, cents, code", [
    ("issue_refund", "cust-31", 40_000, "over_cap"),
    ("issue_refund", "cust-44", 2_000, "wrong_customer"),
    ("issue_refund", "cust-31", -40_000, "bad_amount"),
    ("issue_refund", "cust-31", 0, "bad_amount"),
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
    refund(door, token)
    assert pay.ledger == [("issue_refund", "ORD-004830", 2_000)]
    event = log.events[0]
    assert (event["agent"], event["decision"], event["trace"]) == (
        "actioner", "allow", "trace-1")
    with pytest.raises(Refused):                       # a second use
        refund(door, token)
    assert log.events[1]["decision"] == "deny:unknown_or_used"
    assert len(pay.ledger) == 1


def test_a_denied_call_never_reaches_the_payments_service():
    _, broker, log, pay, door = setup()
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    with pytest.raises(Refused):
        refund(door, token, cents=40_000)
    assert pay.ledger == []
    assert log.events[0]["decision"] == "deny:over_cap"


def test_a_stranger_order_inside_the_callers_session_pays_nothing():
    _, broker, log, pay, door = setup()
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    with pytest.raises(Refused) as err:                # $49, under the cap
        refund(door, token, order="ORD-007777", cents=4_900)
    assert err.value.code == "not_authorized" and pay.ledger == []
    assert log.events[-1]["decision"] == "deny:not_authorized"


def test_a_cap_per_key_is_not_a_cap_per_day():
    _, broker, _, pay, door = setup()
    seen = []
    for n in range(3):                           # three $40 refunds
        token = broker.issue("actioner", "issue_refund", f"t{n}", "cust-31")
        try:
            refund(door, token, cents=4_000)
            seen.append("paid")
        except Refused as refusal:
            seen.append(refusal.code)
    assert seen == ["paid", "paid", "needs_approval"]
    assert sum(cents for _, _, cents in pay.ledger) == 8_000


def test_an_order_is_never_refunded_past_its_total():
    _, broker, _, pay, door = setup()
    for n, cents in enumerate([5_000, 5_000]):        # a $99 order
        token = broker.issue("actioner", "issue_refund", f"t{n}", "cust-44",
                             max_cents=cents)
        if n == 0:
            refund(door, token, "ORD-007777", cents, "cust-44")
        else:
            with pytest.raises(Refused) as err:
                refund(door, token, "ORD-007777", cents, "cust-44")
            assert err.value.code == "amount_too_high"
    assert pay.ledger == [("issue_refund", "ORD-007777", 5_000)]


def test_chapter_6_kept_two_fields_and_the_record_keeps_more():
    state = new_state(0)
    call_tool(state, "reschedule_delivery", order_id=ord_id(0),
              window="Thu 10:00-12:00")
    assert set(state["audit_log"][0]) == {"tool", "target"}
    log = AuditLog(FakeClock())
    event = log.record(agent="actioner", version="v7", tool="x", args={},
                       decision="allow", trace="t", task="k")
    assert {"agent", "version", "decision", "approver", "trace",
            "seq", "prev", "hash"} <= set(event)
    assert len(event["hash"]) == 64        # no short seal to grind


# Attacks on the log. The attacker can write the store; the key is not
# in it. Each attack used to pass the old unkeyed, 8-character chain.

def sealed_log(n=5):
    log = AuditLog(FakeClock(), Sealer(b"held by the key service"))
    for k in range(n):
        log.record(agent="actioner", version="v7", tool="issue_refund",
                   args={"order_id": f"ORD-00483{k}", "amount_cents": 2_000},
                   decision="allow", trace="t", task=f"k{k}")
    return log


def reseal(events, start, key=b"a key of the editor's own"):
    """A careful editor: recompute every seal from `start` on."""
    rogue = Sealer(key)
    rogue.head = (start, events[start - 1]["hash"] if start else "0" * 64)
    for i in range(start, len(events)):
        body = {k: v for k, v in events[i].items()
                if k not in ("seq", "prev", "hash")}
        events[i] = rogue.seal(body)


def test_editing_an_old_record_breaks_the_chain_at_that_record():
    log = sealed_log()
    assert log.verify() is None
    log.events[1]["args"]["amount_cents"] = 100
    assert log.verify() == 1


def test_an_edit_with_every_later_hash_recomputed_is_still_caught():
    log = sealed_log()
    log.events[2]["args"] = {"order_id": "ORD-004832",
                             "amount_cents": 40_000}
    reseal(log.events, 2)
    assert log.verify() == 2


def test_dropping_the_newest_records_is_caught_against_the_head():
    log = sealed_log()
    del log.events[-2:]
    assert log.verify() == 3                 # records 3 and 4 are gone
    log.events = []
    assert log.verify() == 0


def test_deleting_a_middle_record_and_resealing_the_tail_is_caught():
    log = sealed_log()
    del log.events[2]
    assert log.verify() == 2
    reseal(log.events, 2)
    assert log.verify() == 2


def test_swapping_two_records_is_caught():
    log = sealed_log()
    log.events[1], log.events[2] = log.events[2], log.events[1]
    assert log.verify() == 1


def test_what_the_chain_cannot_see_a_payment_that_skipped_the_door():
    _, broker, log, pay, door = setup()
    for k in range(4):
        token = broker.issue("actioner", "issue_refund", f"t{k}", "cust-31")
        refund(door, token, order=f"ORD-0048{30 + k}")
    assert log.coverage(pay.ledger) == 1.0
    pay.issue_refund("ORD-004899", 2_500)           # bypasses the door
    assert log.verify() is None                     # the chain is fine
    assert log.coverage(pay.ledger) == pytest.approx(0.8)
    assert log.coverage([]) == 1.0


def test_coverage_matches_the_amount_as_well_as_the_order():
    _, broker, log, pay, door = setup()
    token = broker.issue("actioner", "issue_refund", "t1", "cust-31")
    refund(door, token, cents=2_500)                  # $25 on the record
    pay.issue_refund("ORD-004830", 40_000)            # $400 in the bank
    assert log.coverage(pay.ledger) == pytest.approx(0.5)
