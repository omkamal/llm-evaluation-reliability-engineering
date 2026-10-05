"""Test the backup like a primary, before the outage."""
from ch02_trust_outputs.refund import ToolError, validate_refund_args

# (customer, order, cents owed): a miniature of Relay's refund cases
CASES = [("cust-17", "ORD-004829", 1500), ("cust-17", "ORD-004829", 800),
         ("cust-22", "ORD-004830", 1500), ("cust-22", "ORD-004830", 4000),
         ("cust-22", "ORD-004830", 250)]


def model_a(order, cents):
    """Provider A with prompt A: arguments in the shape Relay expects."""
    return {"order_id": order, "reason": "damaged", "amount_cents": cents}


def model_b_untuned(order, cents):
    """Provider B given prompt A: puts dollars where cents belong."""
    return {"order_id": order, "reason": "damaged",
            "amount": cents / 100}


def model_b_tuned(order, cents):
    """Provider B with its own prompt variant: integer cents, as asked."""
    return model_a(order, cents)


def dry_run(model, cases=CASES):
    """Run the cases through Chapter 2's checks: (passed, total, why)."""
    passed, first = 0, None
    for user, order, cents in cases:
        checked = validate_refund_args(model(order, cents), user)
        if isinstance(checked, ToolError):
            first = first or f"{checked.layer}: {checked.code}"
        else:
            passed += 1
    return passed, len(cases), first
