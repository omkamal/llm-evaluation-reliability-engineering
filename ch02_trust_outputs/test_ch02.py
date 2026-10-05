"""Chapter 2 as tests. `pytest -q ch02_trust_outputs`"""
import threading

import pytest

from ch02_trust_outputs.gateway import Gateway
from ch02_trust_outputs.idem import KeyReused, Payments, RefundService, make_key
from ch02_trust_outputs.metrics import Day
from ch02_trust_outputs.refund import (RefundArgs, ToolError, needs_approval,
                                       validate_refund_args)
from ch02_trust_outputs.repair import MAX_ATTEMPTS, Failure, Reply, get_ticket
from ch02_trust_outputs.schema import BLACK_FRIDAY, GOOD_TICKET, Ticket
from ch02_trust_outputs.triage import balanced, classify, schema_suspects

V = {"prompt_version": "v12", "model_version": "a-large-v1"}


def scripted(*replies):
    it, seen = iter(replies), []

    def call(prompt):
        seen.append(prompt)
        return next(it)
    call.seen = seen
    return call


def test_valid_json_is_not_valid_data():
    import json
    json.loads(BLACK_FRIDAY)                       # parses perfectly
    gw = Gateway()
    assert gw.check(BLACK_FRIDAY, **V) is None     # and is still refused
    kinds = {(loc, kind) for loc, kind, _ in gw.quarantine[0].errors}
    assert kinds == {("severity", "literal_error"), ("affected_services", "too_short")}


def test_quarantine_keeps_the_evidence():
    gw = Gateway()
    gw.check(BLACK_FRIDAY, **V)
    q = gw.quarantine[0]
    assert q.raw == BLACK_FRIDAY and q.prompt_version == "v12" and q.model_version == "a-large-v1"
    gw.check(GOOD_TICKET, **V)
    assert gw.quarantine_rate == 0.5


def test_unknown_values_are_never_silently_mapped():
    assert Gateway().check(BLACK_FRIDAY.replace("[]", '["web"]'), **V) is None


def test_an_approved_alias_is_applied_and_counted():
    gw = Gateway(aliases={"urgent": "critical"})
    ticket = gw.check(BLACK_FRIDAY.replace("[]", '["web"]'), **V)
    assert ticket.severity == "critical" and gw.aliased == 1


def test_invalid_json_is_quarantined_with_aliases_on():
    gw = Gateway(aliases={"urgent": "critical"})
    assert gw.check('{"severity": "crit', **V) is None
    assert gw.quarantine[0].errors[0][1] == "json_invalid"


def test_extra_fields_are_rejected():
    gw = Gateway()
    assert gw.check(GOOD_TICKET[:-1] + ', "priority": 1}', **V) is None
    assert gw.quarantine[0].errors[0][1] == "extra_forbidden"


def test_the_schema_feeds_the_prompt_too():
    props = Ticket.model_json_schema()["properties"]
    assert set(props) == {"severity", "affected_services", "description", "timestamp"}
    assert "critical" in props["severity"]["description"]


def test_repair_succeeds_on_the_second_reply_with_error_details():
    call = scripted(Reply(BLACK_FRIDAY), Reply(GOOD_TICKET))
    assert get_ticket("go", call).severity == "critical"
    assert "affected_services" in call.seen[1] and "urgent" in call.seen[1]


def test_repair_is_capped_and_ends_in_a_typed_failure():
    call = scripted(*[Reply(BLACK_FRIDAY)] * 9)
    out = get_ticket("go", call)
    assert isinstance(out, Failure) and out.reason == "invalid_after_repair"
    assert len(call.seen) == MAX_ATTEMPTS


def test_truncation_skips_repair():
    call = scripted(Reply('{"severity": "cri', finish_reason="length"))
    out = get_ticket("go", call)
    assert out.reason == "truncated" and len(call.seen) == 1


def test_triage_tells_truncation_from_validation():
    assert classify('{"a": [1, 2', "stop", 40, 512) == "truncation"
    assert classify("{}", "length", 10, 512) == "truncation"
    assert classify("{}", "stop", 512, 512) == "truncation"
    assert classify('{"timestamp": "this morning"}', "stop", 30, 512) == "validation"
    assert balanced('{"a": "}"}') and not balanced('{"a": [')


def test_the_same_field_failing_everywhere_is_a_schema_design_problem():
    gw = Gateway()
    bad = GOOD_TICKET.replace("2026-11-27T09:14:00Z", "this morning")
    for _ in range(10):
        gw.check(bad, **V)
    gw.check(BLACK_FRIDAY, **V)
    assert schema_suspects(gw.quarantine) == {"timestamp": 10}


def test_the_four_numbers():
    n = Day(970, 20, 4, 6).numbers()
    assert round(n["first-pass validity"], 3) == 0.97
    assert round(n["repair success"], 3) == round(20 / 26, 3)
    assert Day(810, 120, 20, 50).numbers()["first-pass validity"] == 0.81


@pytest.mark.parametrize("raw,user,layer,code", [
    ({"order_id": "4829", "amount_cents": 4999, "reason": "late"}, "cust-17", "schema", "invalid_arguments"),
    ({"order_id": "ORD-004829", "amount_cents": 49.99, "reason": "late"}, "cust-17", "schema", "invalid_arguments"),
    ({"order_id": "ORD-004829", "amount_cents": 100, "reason": "late", "tip": 1}, "cust-17", "schema", "invalid_arguments"),
    ({"order_id": "ORD-999999", "amount_cents": 4999, "reason": "late"}, "cust-17", "referential", "order_not_found"),
    ({"order_id": "ORD-004829", "amount_cents": 4999, "reason": "late"}, "cust-99", "authorization", "not_authorized"),
    ({"order_id": "ORD-004829", "amount_cents": 5999, "reason": "late"}, "cust-17", "business", "amount_too_high"),
])
def test_each_layer_rejects_with_a_specific_error(raw, user, layer, code):
    err = validate_refund_args(raw, user)
    assert isinstance(err, ToolError) and (err.layer, err.code) == (layer, code)


def test_the_business_error_tells_the_model_how_to_fix_it():
    err = validate_refund_args({"order_id": "ORD-004829", "amount_cents": 5999, "reason": "late"}, "cust-17")
    assert err.message == "max 4999 cents"


def test_a_valid_call_passes_and_approval_depends_on_the_amount():
    ok = validate_refund_args({"order_id": "ORD-004829", "amount_cents": 4999, "reason": "late"}, "cust-17")
    assert isinstance(ok, RefundArgs) and not needs_approval(ok)
    big = RefundArgs(order_id="ORD-004830", amount_cents=5001, reason="other")
    assert needs_approval(big)


def test_a_retry_without_a_key_pays_twice_with_a_key_once():
    args = RefundArgs(order_id="ORD-004829", amount_cents=4999, reason="late")
    naive = Payments()
    naive.refund(args.order_id, args.amount_cents)
    naive.refund(args.order_id, args.amount_cents)
    assert len(naive.calls) == 2
    pay = Payments()
    svc = RefundService(pay)
    key = make_key("conv-77", args.order_id)
    assert svc.issue_refund(args, key) == svc.issue_refund(args, key)
    assert len(pay.calls) == 1


def test_simultaneous_retries_cannot_both_slip_through():
    args = RefundArgs(order_id="ORD-004829", amount_cents=4999, reason="late")
    pay = Payments()
    svc = RefundService(pay)
    key = make_key("conv-77", args.order_id)
    threads = [threading.Thread(target=svc.issue_refund, args=(args, key)) for _ in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(pay.calls) == 1


def test_a_different_conversation_is_a_different_refund():
    assert make_key("conv-77", "ORD-004829") != make_key("conv-78", "ORD-004829")


def test_a_reused_key_with_a_different_request_is_refused_not_replayed():
    pay = Payments()
    svc = RefundService(pay)
    first = RefundArgs(order_id="ORD-004829", amount_cents=1000, reason="damaged")
    other = RefundArgs(order_id="ORD-004829", amount_cents=500, reason="late")
    key = make_key("conv-77", first.order_id)
    svc.issue_refund(first, key)
    with pytest.raises(KeyReused):
        svc.issue_refund(other, key)
    assert pay.calls == [("ORD-004829", 1000)]       # nothing was paid twice


def test_a_retry_that_picks_another_reason_is_still_a_replay():
    pay = Payments()
    svc = RefundService(pay)
    a = RefundArgs(order_id="ORD-004829", amount_cents=1000, reason="damaged")
    b = RefundArgs(order_id="ORD-004829", amount_cents=1000, reason="other")
    key = make_key("conv-77", a.order_id)
    assert svc.issue_refund(a, key) == svc.issue_refund(b, key)
    assert len(pay.calls) == 1
