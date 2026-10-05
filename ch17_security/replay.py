"""Replay INC-6 against two guards; read the payments, not the words."""
from ch02_trust_outputs.idem import Payments, RefundService, make_key
from ch02_trust_outputs.refund import RefundArgs
from ch17_security.attacks import INC6_NOTE
from ch17_security.guards import INC6, Ctx, decide
from ch17_security.world import Session, ToolCall

SESSION = Session("cust-17", verified=True)    # the logged-in customer


def fooled_call(text=INC6_NOTE):
    """What a Planner that believed the text would ask the Actioner for:
    the same call, whatever the wording."""
    return ToolCall("issue_refund",
                    {"order_id": "ORD-004831", "amount_cents": 40_000,
                     "reason": "other"},
                    read_text=text,
                    claimed_customer="cust-31")   # the note's claim


def execute(call, ctx, service):
    """Run a refund only if the chain allows it. Returns the decision."""
    verdict = decide(call, ctx)
    if verdict.verdict == "allow" and call.name == "issue_refund":
        args = RefundArgs.model_validate(call.args)
        service.issue_refund(args, make_key("conv-1", args.order_id))
    return verdict


def replay(layers=None):
    """One fooled call through one guard; returns (decision, payouts)."""
    payments = Payments()
    ctx = Ctx(SESSION) if layers is None else Ctx(SESSION, layers=layers)
    verdict = execute(fooled_call(), ctx, RefundService(payments))
    return verdict, payments.calls


def replay_inc6():
    return replay(list(INC6))
