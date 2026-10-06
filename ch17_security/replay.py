"""Replay INC-6 against two guards; read the payments, not the words."""
from ch02_trust_outputs.idem import (Payments, RefundService, make_key,
                                     new_request_id)
from ch02_trust_outputs.refund import RefundArgs
from ch17_security.attacks import INC6_NOTE
from ch17_security.guards import INC6, Ctx, decide
from ch17_security.world import Session, ToolCall, new_orders

SESSION = Session("cust-17", verified=True)    # the logged-in customer


def fooled_call(text=INC6_NOTE):
    """What a Planner that believed the text would ask the Actioner for:
    the same call, whatever the wording."""
    return ToolCall("issue_refund",
                    {"order_id": "ORD-004831", "amount_cents": 40_000,
                     "reason": "other"},
                    read_text=text,
                    claimed_customer="cust-31")   # the note's claim


def execute(call, ctx, service=None):
    """Run a call only if the chain allows it. Returns the decision.
    A refund is paid by ctx's ledger, which books it and checks the
    order total and the day line again as it pays. A `service` given
    here is paid the old way, knowing no totals and no customer: the
    refund path INC-6 had."""
    verdict = decide(call, ctx)
    if verdict.verdict != "allow":
        return verdict
    ctx.used[call.name] += 1
    if call.name == "issue_refund":
        args = RefundArgs.model_validate(call.args)
        key = make_key(ctx.conversation, args.order_id, new_request_id())
        if service is None:
            ctx.ledger.issue_refund(args, key,
                                    customer_id=ctx.session.customer_id)
        else:
            service.issue_refund(args, key)
    return verdict


def replay(layers=None, service=None):
    """One fooled call through one guard; returns (decision, payouts)."""
    ctx = Ctx(SESSION) if layers is None else Ctx(SESSION, layers=layers)
    verdict = execute(fooled_call(), ctx, service)
    return verdict, (service or ctx.ledger).payments.calls


def replay_inc6():
    return replay(list(INC6), RefundService(Payments()))


def split_refunds(times, cents, order="ORD-004832"):
    """One customer asks for the same small refund again and again, each
    time in a new chat. Returns (verdicts, cents paid)."""
    orders = new_orders()
    ledger = Ctx(SESSION, orders=orders).ledger    # shared: the day
    verdicts = []
    for chat in range(times):
        ctx = Ctx(SESSION, orders=orders, ledger=ledger,
                  conversation=f"conv-{chat}")
        call = ToolCall("issue_refund", {"order_id": order,
                                         "amount_cents": cents,
                                         "reason": "other"})
        verdicts.append(execute(call, ctx).verdict)
    return verdicts, sum(c for _, c in ledger.payments.calls)
