"""Detection that would have caught INC-6.

A band on the share of tasks with a credit (Chapter 13) cannot see one
wrong credit among a normal few. A rule on each credit can: one event
is enough to page, with no window to fill."""
import json

from ch02_trust_outputs.refund import RefundArgs, needs_approval


def credits_without_approver(spans):
    """Pages (time, text) for every issue_refund that Chapter 2's limits
    send to a person ($50 a refund, $100 a customer a day) but that ran
    with no approver on its span. Read from the trace, after the fact,
    so it also catches a gate that was missing or bypassed."""
    pages, paid = [], {}
    for sp in sorted(spans, key=lambda s: s.start):
        a = sp.attributes
        if a.get("gen_ai.tool.name") != "issue_refund":
            continue
        args = RefundArgs.model_validate(json.loads(a["relay.tool.args"]))
        day = (a.get("enduser.id"), int(sp.start // 86400))
        today = paid.get(day, 0)
        paid[day] = today + args.amount_cents
        if needs_approval(args, today) and not a.get("relay.approver"):
            pages.append((sp.start, f"${args.amount_cents / 100:.2f} "
                          "needed a person, none approved"))
    return pages
