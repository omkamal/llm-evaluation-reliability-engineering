"""Every Chapter 2 idea, with its printed output.   python3 -m ch02_trust_outputs.demo"""
from pydantic import ValidationError

from ch02_trust_outputs.gateway import Gateway
from ch02_trust_outputs.idem import (KeyReused, Payments, RefundService, ReplyLost,
                                     make_key, new_request_id)
from ch02_trust_outputs.metrics import Day
from ch02_trust_outputs.refund import Order, RefundArgs, needs_approval, validate_refund_args
from ch02_trust_outputs.repair import MAX_ATTEMPTS, Failure, Reply, get_ticket
from ch02_trust_outputs.schema import BLACK_FRIDAY, GOOD_TICKET, Ticket
from ch02_trust_outputs.triage import classify, schema_suspects


def scripted(*replies):
    it, seen = iter(replies), []
    def call(prompt):
        seen.append(prompt)
        return next(it)
    call.seen = seen
    return call


def main():
    print("== parse passes, validate fails")
    try:
        Ticket.model_validate_json(BLACK_FRIDAY)
    except ValidationError as e:
        for err in e.errors():
            print(f"{err['type']}: {err['msg']}")

    print("== the gateway quarantines instead of dropping")
    gw = Gateway()
    gw.check(BLACK_FRIDAY, prompt_version="v12", model_version="a-large-v1")
    gw.check(GOOD_TICKET, prompt_version="v12", model_version="a-large-v1")
    q = gw.quarantine[0]
    print(f"quarantined: {[(loc, kind) for loc, kind, _ in q.errors]}")
    print(f"kept with it: prompt {q.prompt_version}, model {q.model_version}")
    print(f"quarantine rate: {gw.quarantine_rate:.0%}")

    print("== an explicit, counted mapping is allowed; a silent one is not")
    gw2 = Gateway(aliases={"urgent": "critical"})
    fixed = BLACK_FRIDAY.replace('"affected_services": []', '"affected_services": ["checkout"]')
    print(gw2.check(fixed, prompt_version="v12", model_version="a-large-v1").severity,
          f"(aliased {gw2.aliased} time)")

    print("== repair, bounded")
    call = scripted(Reply(BLACK_FRIDAY), Reply(GOOD_TICKET))
    result = get_ticket("Draft a ticket.", call)
    print(f"repaired after {len(call.seen) - 1} repair call: severity={result.severity}")
    stuck = scripted(*[Reply(BLACK_FRIDAY)] * 5)
    out = get_ticket("Draft a ticket.", stuck)
    print(f"{out.reason} after {len(stuck.seen)} calls (cap {MAX_ATTEMPTS})")
    cut = scripted(Reply('{"severity": "criti', finish_reason="length"))
    out = get_ticket("Draft a ticket.", cut)
    print(f"{out.reason} after {len(cut.seen)} call: repair skipped")

    print("== truncation or schema design?")
    print(classify('{"severity": "criti', "length", 512, 512))
    print(classify('{"severity": "high", "timestamp": "this morning"}', "stop", 40, 512))
    bad = '{"severity": "high", "affected_services": ["web"], "description": "d", "timestamp": "this morning"}'
    gw3 = Gateway()
    for _ in range(40):
        gw3.check(bad, prompt_version="v13", model_version="a-large-v1")
    for _ in range(5):
        gw3.check(BLACK_FRIDAY, prompt_version="v13", model_version="a-large-v1")
    print(schema_suspects(gw3.quarantine))

    print("== four numbers")
    for name, day in (("normal day", Day(986, 9, 2, 3)), ("after prompt v13", Day(810, 138, 2, 50))):
        print(name + ": " + ", ".join(f"{k} {v:.1%}" for k, v in day.numbers().items()))

    print("== four layers of argument checks")
    cases = [
        ({"order_id": "4829", "amount_cents": 4999, "reason": "late"}, "cust-17"),
        ({"order_id": "ORD-999999", "amount_cents": 4999, "reason": "late"}, "cust-17"),
        ({"order_id": "ORD-004829", "amount_cents": 4999, "reason": "late"}, "cust-99"),
        ({"order_id": "ORD-004829", "amount_cents": 5999, "reason": "late"}, "cust-17"),
        ({"order_id": "ORD-004829", "amount_cents": 4999, "reason": "late"}, "cust-17"),
    ]
    for raw, user in cases:
        res = validate_refund_args(raw, user)
        print(f"{res.layer}: {res.code}" if hasattr(res, "layer") else f"accepted, approval needed: {needs_approval(res)}")

    print("== idempotency")
    args = RefundArgs(order_id="ORD-004829", amount_cents=4999, reason="late")
    naive = Payments()
    naive.refund(args.order_id, args.amount_cents)
    naive.refund(args.order_id, args.amount_cents)      # the retry after a timeout
    print(f"without a key: payments ran {len(naive.calls)} times")
    pay = Payments()
    svc = RefundService(pay)
    key = make_key("conv-77", args.order_id)
    first, again = svc.issue_refund(args, key), svc.issue_refund(args, key)
    print(f"with a key: same answer {first == again}, payments ran {len(pay.calls)} time")
    other = RefundArgs(order_id="ORD-004829", amount_cents=500, reason="late")
    try:
        svc.issue_refund(other, key)
    except KeyReused:
        print(f"same key, other amount: refused, payments still {len(pay.calls)}")
    lost = ReplyLost()                        # pays, then the answer is lost
    svc = RefundService(lost)
    key = make_key("conv-77", args.order_id, new_request_id())
    try:
        svc.issue_refund(args, key)
    except TimeoutError:
        again = svc.issue_refund(args, key)  # the retry asks, it does not pay
    print(f"reply lost, then a retry: payments ran {len(lost.calls)} time")
    pay = Payments()
    svc = RefundService(pay, orders={"ORD-004829": Order("cust-17", 4_999)})
    chats = [svc.issue_refund(args, make_key(conv, args.order_id, new_request_id()),
                              "cust-17") for conv in ("conv-77", "conv-81")]
    print(f"two chats refund the whole order: paid {len(pay.calls)}, "
          f"then {chats[1].code}")
    pay = Payments()
    svc = RefundService(pay, orders={"ORD-004830": Order("cust-22", 12_000)})
    forty = RefundArgs(order_id="ORD-004830", amount_cents=4_000, reason="late")
    out = [svc.issue_refund(forty, make_key("conv-90", forty.order_id, new_request_id()),
                            "cust-22") for _ in range(3)]
    print(f"three $40 refunds in a day: paid {len(pay.calls)}, then {out[2].code}")


if __name__ == "__main__":
    main()
