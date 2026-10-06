"""Chapter 2 as tests. `pytest -q ch02_trust_outputs`"""
import threading

import pytest

from ch02_trust_outputs.gateway import Gateway
from datetime import date

from ch02_trust_outputs.idem import (KeyReused, Payments, RefundPending,
                                     RefundService, ReplyLost, make_key,
                                     new_request_id)
from ch02_trust_outputs.metrics import Day
from ch02_trust_outputs.refund import (Order, RefundArgs, ToolError,
                                       needs_approval, validate_refund_args)
from ch02_trust_outputs.repair import MAX_ATTEMPTS, Failure, Reply, get_ticket
from ch02_trust_outputs.schema import BLACK_FRIDAY, GOOD_TICKET, Ticket
from ch02_trust_outputs.triage import (balanced, classify, schema_suspects,
                                       unclosed)

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
    bad = GOOD_TICKET.replace("2025-11-28T09:14:00Z", "this morning")
    for _ in range(10):
        gw.check(bad, **V)
    gw.check(BLACK_FRIDAY, **V)
    assert schema_suspects(gw.quarantine) == {"timestamp": 10}


def test_the_four_numbers():
    n = Day(986, 9, 2, 3).numbers()
    assert round(n["first-pass validity"], 3) == 0.986    # meets Ch 12's 98%
    assert round(n["repair success"], 3) == 0.75
    v13 = Day(810, 138, 2, 50).numbers()
    assert v13["first-pass validity"] == 0.81
    assert v13["truncation rate"] == n["truncation rate"]  # not truncation


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

    def retry():
        try:
            svc.issue_refund(args, key)
        except RefundPending:       # the first is still paying: wait
            pass
    threads = [threading.Thread(target=retry) for _ in range(20)]
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


# ---- added in the review round: strict contracts, safe refunds (D1)

@pytest.mark.parametrize("amount", [True, "4999", 4999.0, "4_999"])
def test_strict_mode_never_converts_an_amount(amount):
    raw = {"order_id": "ORD-004829", "amount_cents": amount, "reason": "late"}
    err = validate_refund_args(raw, "cust-17")
    assert isinstance(err, ToolError) and err.layer == "schema"


@pytest.mark.parametrize("stamp", ["0", "1732698840", '"2025-11-28"',
                                   '"2025-11-28T09:14:00"'])
def test_strict_mode_never_invents_a_timestamp(stamp):
    raw = GOOD_TICKET.replace('"2025-11-28T09:14:00Z"', stamp)
    assert Gateway().check(raw, **V) is None


def test_blank_text_is_not_text():
    gw = Gateway()
    assert gw.check(GOOD_TICKET.replace('"Checkout is down for all customers"',
                                        '" "'), **V) is None
    assert gw.check(GOOD_TICKET.replace('["checkout"]', '[""]'), **V) is None
    assert gw.check(GOOD_TICKET, **V).timestamp.year == 2025


@pytest.mark.parametrize("raw", ["[1, 2]", "null", '"hello"',
                                 '{"severity": ["urgent"]}'])
def test_alias_mode_quarantines_odd_output_instead_of_crashing(raw):
    gw = Gateway(aliases={"urgent": "critical"})
    assert gw.check(raw, **V) is None and len(gw.quarantine) == 1


def test_a_refusal_is_reported_not_repaired():
    call = scripted(Reply("I can't help with that.", finish_reason="refusal"))
    out = get_ticket("go", call)
    assert out.reason == "refused" and len(call.seen) == 1


def test_an_extra_closing_bracket_is_not_truncation():
    assert classify('{"severity": "high"}}', "stop", 10, 512) == "validation"
    assert not unclosed('{"a": "say \\"hi\\""}')     # escaped quotes
    assert unclosed('{"a": "say \\"hi')


def test_a_lost_reply_and_a_retry_pay_once():
    args = RefundArgs(order_id="ORD-004829", amount_cents=4999, reason="late")
    pay = ReplyLost()                  # pays, then the reply is lost
    svc = RefundService(pay)
    key = make_key("conv-77", args.order_id, new_request_id())
    with pytest.raises(TimeoutError):
        svc.issue_refund(args, key)
    assert svc.issue_refund(args, key)["refund_id"] == "re_001"
    assert len(pay.calls) == 1 and pay.find(key) is not None   # key travelled


def test_a_retry_while_the_first_call_is_paying_is_told_to_wait():
    args = RefundArgs(order_id="ORD-004829", amount_cents=4999, reason="late")
    key = make_key("conv-77", args.order_id, "r1")
    seen = []

    class Slow(Payments):
        def refund(self, *a, **kw):    # a retry lands mid-payment
            with pytest.raises(RefundPending):
                svc.issue_refund(args, key)
            seen.append("waited")
            return super().refund(*a, **kw)
    pay = Slow()
    svc = RefundService(pay)
    svc.issue_refund(args, key)
    assert seen == ["waited"] and len(pay.calls) == 1


def test_two_chats_cannot_each_refund_the_whole_order():
    orders = {"ORD-004829": Order("cust-17", 4_999)}
    pay = Payments()
    svc = RefundService(pay, orders=orders)
    args = RefundArgs(order_id="ORD-004829", amount_cents=4_999, reason="late")
    first = svc.issue_refund(args, make_key("conv-77", "ORD-004829", "r1"))
    second = svc.issue_refund(args, make_key("conv-81", "ORD-004829", "r2"))
    assert first["amount_cents"] == 4_999
    assert (second.code, second.message) == ("amount_too_high", "max 0 cents")
    assert orders["ORD-004829"].refunded_cents == 4_999 and len(pay.calls) == 1
    # and layer 4 now sees it too
    raw = {"order_id": "ORD-004829", "amount_cents": 1, "reason": "late"}
    assert validate_refund_args(raw, "cust-17", orders).code == "amount_too_high"


def test_five_concurrent_chats_pay_one_whole_order_refund():
    orders = {"ORD-004829": Order("cust-17", 4_999)}
    pay = Payments()
    svc = RefundService(pay, orders=orders)
    args = RefundArgs(order_id="ORD-004829", amount_cents=4_999, reason="late")
    barrier = threading.Barrier(5)

    def chat(i):
        barrier.wait()
        svc.issue_refund(args, make_key(f"conv-{i}", "ORD-004829", f"r{i}"))
    threads = [threading.Thread(target=chat, args=(i,)) for i in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(pay.calls) == 1


def test_three_40_dollar_refunds_do_not_all_slip_under_the_line():
    day = [date(2025, 11, 28)]
    orders = {"ORD-004830": Order("cust-22", 12_000)}
    pay = Payments()
    svc = RefundService(pay, orders=orders, today=lambda: day[0])
    forty = RefundArgs(order_id="ORD-004830", amount_cents=4_000, reason="late")
    out = [svc.issue_refund(forty, make_key("c", "ORD-004830", f"r{i}"),
                            "cust-22") for i in range(3)]
    assert len(pay.calls) == 2 and out[2].code == "needs_approval"
    assert svc.paid_today("cust-22") == 8_000
    # a person approves the held one, under the same key
    ok = svc.issue_refund(forty, make_key("c", "ORD-004830", "r2"), "cust-22",
                          approved_by="priya")
    assert ok["amount_cents"] == 4_000 and len(pay.calls) == 3
    day[0] = date(2025, 11, 29)        # a new day starts a new total
    assert svc.paid_today("cust-22") == 0


def test_the_daily_line_is_a_pure_function_too():
    forty = RefundArgs(order_id="ORD-004830", amount_cents=4_000, reason="late")
    assert not needs_approval(forty) and not needs_approval(forty, 6_000)
    assert needs_approval(forty, 6_001)


def test_two_legitimate_refunds_in_one_chat_need_two_request_ids():
    pay = Payments()
    svc = RefundService(pay)
    damage = RefundArgs(order_id="ORD-004830", amount_cents=1_000,
                        reason="damaged")
    late = RefundArgs(order_id="ORD-004830", amount_cents=500, reason="late")
    short = make_key("conv-77", "ORD-004830")           # Try it 3
    svc.issue_refund(damage, short)
    with pytest.raises(KeyReused):
        svc.issue_refund(late, short)
    svc.issue_refund(late, make_key("conv-77", "ORD-004830", new_request_id()))
    assert pay.calls == [("ORD-004830", 1_000), ("ORD-004830", 500)]


def test_a_key_built_from_the_reason_pays_twice_on_a_retry():
    pay = Payments()
    svc = RefundService(pay)
    a = RefundArgs(order_id="ORD-004829", amount_cents=1_000, reason="damaged")
    b = RefundArgs(order_id="ORD-004829", amount_cents=1_000, reason="other")
    for args in (a, b):                # the retry picked another reason
        svc.issue_refund(args, f"refund:conv-77:ORD-004829:{args.reason}")
    assert len(pay.calls) == 2         # why the key never holds the reason


def test_old_callers_still_get_a_plain_idempotent_service():
    # Chapters 10 and 17 call RefundService(payments).issue_refund(args, key)
    pay = Payments()
    big = RefundArgs(order_id="ORD-004831", amount_cents=40_000, reason="other")
    assert RefundService(pay).issue_refund(big, "k")["amount_cents"] == 40_000
