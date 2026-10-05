"""The one door: check the token, write the record, then run the tool."""
from ch18_governance.broker import Refused


class Payments:
    """A stand-in for payments, with a ledger of its own."""

    def __init__(self):
        self.ledger = []          # what the bank saw

    def issue_refund(self, order_id, amount_cents, reason="other"):
        self.ledger.append(("issue_refund", order_id))
        return f"refunded {amount_cents} cents on {order_id}"


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
        return self.tools[tool](**args)
