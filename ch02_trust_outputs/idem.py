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


class RefundService:
    def __init__(self, payments):
        self.payments, self.done = payments, {}
        # the lock stands in for a database unique constraint
        self.lock = threading.Lock()

    def issue_refund(self, args, idempotency_key):
        with self.lock:
            if (done := self.done.get(idempotency_key)) is not None:
                return done               # replay: no second payout
            result = self.payments.refund(args.order_id,
                                          args.amount_cents)
            self.done[idempotency_key] = result
            return result


def make_key(conversation_id, order_id):
    return f"refund:{conversation_id}:{order_id}"
