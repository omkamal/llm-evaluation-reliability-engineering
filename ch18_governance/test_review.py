"""Tests for expected loss, routing, the review desk and the loop."""
import pytest
from pydantic import ValidationError

from ch02_trust_outputs.refund import Order
from ch05_judge.agreement import cohen_kappa
from common.clock import FakeClock
from ch18_governance.audit import AuditLog
from ch18_governance.broker import Broker
from ch18_governance.door import Door, Payments
from ch18_governance.measure import loop_metrics, nearest_rank
from ch18_governance.review import (InvalidProposal, ReviewDesk, build_packet,
                                    packet_lines)
from ch18_governance.routing import (Case, break_even_cents,
                                     expected_loss_cents, needs_review,
                                     review_mode, triggers)
from ch18_governance.rubber_stamp import flags, simulate, window_report


def test_the_course_example_expected_loss_is_eight_dollars():
    assert expected_loss_cents(0.02, 40_000) == pytest.approx(800)
    assert expected_loss_cents(0.02, 1_500) == pytest.approx(30)


@pytest.mark.parametrize("dollars, review", [(15, False), (50, False),
                                              (74, False), (76, True),
                                              (400, True)])
def test_a_person_reviews_only_when_the_loss_beats_the_cost(dollars, review):
    assert needs_review(0.02, dollars * 100) is review


def test_break_even_amount_and_error_rate():
    assert break_even_cents(0.02) == pytest.approx(7_500)
    assert break_even_cents(0.03) == pytest.approx(5_000)
    assert 150 / 40_000 == pytest.approx(0.00375)


def make_case(cents=40_000, **kw):
    return Case("case-1", "task-1", "cust-31", "f" * 32, "issue_refund",
                {"order_id": "ORD-004830", "amount_cents": cents,
                 "reason": "other"}, "A refund is proposed.",
                evidence=["owner checked"], **kw)


@pytest.mark.parametrize("kw, expected", [
    ({"cents": 1_500}, []),
    ({"cents": 40_000}, ["high_value"]),
    ({"cents": 2_000, "user_asked": True}, ["user_request"]),
    ({"cents": 2_000, "failures": 2}, ["repeated_failure"]),
    ({"cents": 2_000, "policy_unclear": True}, ["policy_ambiguity"]),
    ({"cents": 2_000, "confidence": 0.5}, ["low_confidence"]),
])
def test_five_triggers(kw, expected):
    assert triggers(make_case(**kw)) == expected


def test_irreversible_actions_block_and_the_rest_go_now():
    assert review_mode("issue_refund") == "block"
    assert review_mode("create_ticket") == "async"


def test_a_packet_must_carry_evidence_and_a_reason():
    case = make_case()
    packet = build_packet(case, 900.0)
    assert packet.risk == "expected loss $8.00, review $1.50"
    assert "  propose: issue_refund(ORD-004830, 40000, other)" in packet_lines(
        packet)
    case.evidence = []
    with pytest.raises(ValidationError):
        build_packet(case, 900.0)
    with pytest.raises(ValidationError):           # nothing triggered it
        build_packet(make_case(cents=1_000), 900.0)


def desk():
    orders = {"ORD-004830": Order("cust-31", 52_000)}
    clock = FakeClock()
    broker, log, pay = Broker(clock), AuditLog(clock), Payments()
    door = Door(broker, log, {"issue_refund": pay.issue_refund})
    return clock, log, pay, ReviewDesk(clock, broker, door, log, orders)


def escalate(d, clock, cents=40_000, priority=1, **kw):
    case = make_case(cents, **kw)
    return d.escalate_to_human("high value",
                               build_packet(case, clock.now() + d.sla),
                               "cust-31", priority)


def test_the_queue_serves_priority_first_then_the_earliest_deadline():
    clock, _, _, d = desk()
    late = escalate(d, clock)
    clock.sleep(60)
    early_normal = escalate(d, clock)
    urgent = escalate(d, clock, priority=0)
    assert [d.next().id for _ in range(3)] == [
        urgent.id, late.id, early_normal.id]


def test_approve_pays_once_and_leaves_two_records_with_the_approver():
    clock, log, pay, d = desk()
    item = escalate(d, clock)
    clock.sleep(300)
    out = d.decide(item, "reviewer-7", "approve")
    assert (out.decision, out.final_cents, out.waited) == (
        "approve", 40_000, 300)
    assert pay.ledger == [("issue_refund", "ORD-004830")]
    assert [e["decision"] for e in log.events] == ["allow", "approve"]
    assert {e["approver"] for e in log.events} == {"reviewer-7"}
    assert out.label()["label"] == "pass"


def test_edit_lowers_the_amount_and_never_raises_it():
    clock, log, pay, d = desk()
    item = escalate(d, clock)
    with pytest.raises(ValueError):
        d.decide(item, "reviewer-7", "edit", edited_cents=45_000)
    assert pay.ledger == []
    out = d.decide(item, "reviewer-7", "edit", edited_cents=2_500)
    assert out.final_cents == 2_500 and out.label()["label"] == "fail"
    assert log.events[0]["args"]["amount_cents"] == 2_500


def test_reject_pays_nothing_and_still_leaves_a_record():
    clock, log, pay, d = desk()
    out = d.decide(escalate(d, clock), "reviewer-7", "reject")
    assert pay.ledger == [] and out.final_cents == 0
    assert [e["decision"] for e in log.events] == ["reject"]


def test_a_person_cannot_approve_a_refund_on_someone_elses_order():
    clock, log, pay, d = desk()
    item = escalate(d, clock)
    item.customer = "cust-99"                    # not the order's owner
    with pytest.raises(InvalidProposal, match="not_authorized"):
        d.decide(item, "reviewer-7", "approve")
    assert pay.ledger == []


def test_the_loop_numbers():
    clock, _, _, d = desk()
    for wait, decision in [(100, "approve"), (200, "approve"),
                           (400, "edit"), (1_000, "reject")]:
        item = escalate(d, clock)
        clock.sleep(wait)
        d.decide(item, "reviewer-7", decision, edited_cents=2_500)
    m = loop_metrics(d.outcomes, tasks=40, sla=900)
    assert m["escalation rate"] == pytest.approx(0.10)
    assert m["override rate"] == pytest.approx(0.5)
    assert m["queue p50 s"] == 200 and m["past SLA"] == pytest.approx(0.25)


def test_nearest_rank_percentiles():
    assert nearest_rank([5, 1, 3, 2, 4], 0.5) == 3
    assert nearest_rank(range(1, 101), 0.95) == 95


def test_a_reviewer_who_approves_everything_has_kappa_zero():
    mine, second = simulate(stamp_after=0)
    verdicts = [d.verdict for d in mine]
    assert set(verdicts) == {"approve"}
    assert cohen_kappa(verdicts, second) == 0.0       # the always-pass judge


def test_the_simulation_flags_the_stamping_windows_and_only_those():
    mine, second = simulate(stamp_after=200)
    seen = []
    for start in range(0, 400, 100):
        report = window_report(mine[start:start + 100],
                               second[start:start + 100])
        seen.append(flags(report))
    assert seen[:2] == [[], []]
    assert seen[2:] == [["override", "probes", "speed"]] * 2


def test_a_careful_reviewer_is_never_flagged():
    mine, second = simulate(stamp_after=None)
    for start in range(0, 400, 100):
        report = window_report(mine[start:start + 100],
                               second[start:start + 100])
        assert flags(report) == []
        assert report["kappa"] > 0.6


def test_the_simulation_is_deterministic():
    a, _ = simulate(stamp_after=200)
    b, _ = simulate(stamp_after=200)
    assert [(d.verdict, round(d.seconds, 3)) for d in a] == [
        (d.verdict, round(d.seconds, 3)) for d in b]


def test_exercises_move_the_line_and_a_half_stamped_window():
    assert break_even_cents(0.03) == pytest.approx(5_000)   # the $50 line
    assert break_even_cents(0.01) == pytest.approx(15_000)
    mine, second = simulate(stamp_after=250)
    report = window_report(mine[200:300], second[200:300])
    assert flags(report) == ["probes"] and report["probes"] == (2, 5)
