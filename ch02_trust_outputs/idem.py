"""A retry must never pay twice. An idempotency key makes the second call a replay."""
import threading


class Payments:
    """Stands in for the payment service. `calls` counts real payouts."""
    def __init__(self):
        self.calls = []

    def refund(self, order_id, amount_cents):
        self.calls.append((order_id, amount_cents))
        return {"refund_id": f"re_{len(self.calls):03d}", "order_id": order_id,
                "amount_cents": amount_cents}


class KeyReused(ValueError):
    """One key, two different requests: a bug in the caller, not a replay."""


class RefundService:
    def __init__(self, payments):
        self.payments, self.done = payments, {}
        # the lock stands in for a database unique constraint
        self.lock = threading.Lock()

    def issue_refund(self, args, idempotency_key):
        # the reason is left out: a retried call may pick another
        what = (args.order_id, args.amount_cents)
        with self.lock:
            if (seen := self.done.get(idempotency_key)) is not None:
                first, result = seen
                if first != what:
                    raise KeyReused(f"{idempotency_key} was used for "
                                    f"{first}, now {what}")
                return result             # replay: no second payout
            result = self.payments.refund(*what)
            self.done[idempotency_key] = (what, result)
            return result


def make_key(conversation_id, order_id):
    return f"refund:{conversation_id}:{order_id}"
