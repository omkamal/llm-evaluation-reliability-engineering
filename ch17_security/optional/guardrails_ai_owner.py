"""Chapter 17 Tool Box: the ownership check as a Guardrails AI validator.

Run once, in a throwaway virtualenv, with guardrails-ai 0.11.0, on
5 October 2026. Not run by pytest or CI:
    python3 -m venv /tmp/grai-venv && /tmp/grai-venv/bin/pip install \
        guardrails-ai==0.11.0
    PYTHONPATH=code /tmp/grai-venv/bin/python \
        code/ch17_security/optional/guardrails_ai_owner.py
"""
import json

from guardrails import Guard, OnFailAction
from guardrails.validators import (FailResult, PassResult, Validator,
                                   register_validator)

from ch17_security.world import new_orders


@register_validator(name="relay/owner-from-session", data_type="string")
class OwnerFromSession(Validator):
    def validate(self, value, metadata):
        call = json.loads(value)
        order = new_orders().get(call["args"]["order_id"])
        if order is None or order.customer_id != metadata["customer_id"]:
            return FailResult(error_message="deny: order is not yours")
        return PassResult()


# record the failure and let our own code decide what to do with it
guard = Guard().use(OwnerFromSession(on_fail=OnFailAction.NOOP))


def check(call, customer_id):
    out = guard.validate(json.dumps(call),
                         metadata={"customer_id": customer_id})
    if out.validation_passed:
        return "allow"
    return out.validation_summaries[0].failure_reason


if __name__ == "__main__":
    for order, cents in (("ORD-004829", 1_999), ("ORD-004831", 40_000)):
        call = {"tool": "issue_refund",
                "args": {"order_id": order, "amount_cents": cents}}
        print(f"{order} {cents}: {check(call, 'cust-17')}")
