"""The one door: check the token, write the record, then run the tool.

The door holds the payments credential; the agents never do. Behind it,
issue_refund runs on Chapter 2's code, for the customer named in the
token (the session), never for one the model names.
"""
from datetime import date

from ch02_trust_outputs import idem
from ch02_trust_outputs.idem import RefundService, make_key
from ch02_trust_outputs.refund import ToolError, validate_refund_args
from ch18_governance.broker import Refused


class Payments(idem.Payments):
    """Chapter 2's stand-in bank. `ledger` is what the bank saw."""

    @property
    def ledger(self):
        return [("issue_refund", order, cents)
                for order, cents in self.calls]

    def issue_refund(self, order_id, amount_cents, reason="other"):
        """What a hotfix script does: straight to the bank, no door."""
        return self.refund(order_id, amount_cents)


class Refunds:
    """issue_refund behind the door: Chapter 2's four layers for the
    session's customer, then its RefundService, which keeps each order's
    running total and allows $100 a customer a day without a person."""

    def __init__(self, payments, orders, today=date.today):
        self.orders = orders
        self.service = RefundService(payments, orders, today)

    def __call__(self, token, order_id, amount_cents, reason="other"):
        args = validate_refund_args(
            {"order_id": order_id, "amount_cents": amount_cents,
             "reason": reason}, token.customer, self.orders)
        if isinstance(args, ToolError):       # e.g. not the caller's order
            return args
        return self.service.issue_refund(
            args, make_key(token.task, order_id),
            customer_id=token.customer, approved_by=token.approver)


class Door:
    def __init__(self, broker, log, tools):
        self.broker, self.log, self.tools = broker, log, tools

    def call(self, token, tool, args, customer, trace, version="v7"):
        who = dict(agent=token.agent, version=version, tool=tool,
                   args=args, trace=trace, task=token.task)
        try:
            self.broker.check(token, tool, customer,
                              args.get("amount_cents", 0))
        except Refused as refusal:
            self.log.record(decision=f"deny:{refusal.code}", **who)
            raise
        self.broker.spend(token)
        self.log.record(decision="allow", approver=token.approver, **who)
        done = self.tools[tool](token, **args)   # the token is the session
        if isinstance(done, ToolError):          # Chapter 2's checks said no
            self.log.record(decision=f"deny:{done.code}", **who)
            raise Refused(done.code)
        return done
