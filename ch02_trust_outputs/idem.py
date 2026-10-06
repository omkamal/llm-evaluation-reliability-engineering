"""A retry must never pay twice. An idempotency key makes the second call a replay.

The key is reserved (a pending record) BEFORE the payment call and travels to
the payment provider, so a timeout followed by a retry cannot pay twice. The
limits are checked again, and the money booked, in the same step as the
reservation, so two chats cannot each refund the whole order.
"""
import threading
import uuid
from collections import Counter
from datetime import date

from ch02_trust_outputs.refund import ToolError, needs_approval

PENDING = "pending"          # key reserved; the payment is not confirmed


class Payments:
    """Stands in for the payment service. `calls` counts real payouts.
    Like a real provider, it keeps the result of every key it has seen."""
    def __init__(self):
        self.calls, self.results = [], {}

    def refund(self, order_id, amount_cents, idempotency_key=None):
        if idempotency_key in self.results:
            return self.results[idempotency_key]   # the provider replays
        self.calls.append((order_id, amount_cents))
        result = {"refund_id": f"re_{len(self.calls):03d}", "order_id": order_id,
                  "amount_cents": amount_cents}
        if idempotency_key is not None:
            self.results[idempotency_key] = result
        return result

    def find(self, idempotency_key):
        """What happened to this key? Its result, or None."""
        return self.results.get(idempotency_key)


class ReplyLost(Payments):
    """Pays, then the answer is lost on the way back: the Black Friday timeout."""
    def __init__(self, times=1):
        super().__init__()
        self.times = times

    def refund(self, *args, **kwargs):
        result = super().refund(*args, **kwargs)
        if self.times:
            self.times -= 1
            raise TimeoutError("the payment service did not answer in time")
        return result


class KeyReused(ValueError):
    """One key, two different requests: a bug in the caller, not a replay."""


class RefundPending(RuntimeError):
    """The first call with this key has not finished: wait, never pay again."""


class RefundService:
    def __init__(self, payments, orders=None, today=date.today):
        self.payments, self.done = payments, {}
        # order totals to re-check at payout (None: not checked here)
        self.orders, self.today = orders, today
        self.per_day = Counter()      # cents booked per (customer, day)
        # the lock stands in for a database unique constraint
        self.lock = threading.Lock()

    def issue_refund(self, args, idempotency_key, customer_id=None,
                     approved_by=None):
        key = idempotency_key
        # the reason is left out: a retried call may pick another
        what = (args.order_id, args.amount_cents)
        with self.lock:
            if (seen := self.done.get(key)) is not None:
                return self.replay(key, what, *seen)
            refused = self.hold(args, customer_id, approved_by)
            if refused:
                return refused                # a ToolError
            self.done[key] = (what, PENDING)  # reserve, then pay
        result = self.payments.refund(*what, idempotency_key=key)
        with self.lock:
            self.done[key] = (what, result)
        return result

    def replay(self, key, what, first, result):
        if first != what:
            raise KeyReused(f"{key} was used for {first}, now {what}")
        if result == PENDING:             # did it pay? ask the provider
            result = self.payments.find(key)
            if result is None:
                raise RefundPending(key)  # still running: wait
            self.done[key] = (what, result)
        return result                     # replay: no second payout

    def hold(self, args, customer_id, approved_by):
        """Inside the lock: check the limits again, then book the money."""
        order = None
        if self.orders is not None:
            order = self.orders.get(args.order_id)
            if order is None:
                return ToolError("referential", "order_not_found",
                                 args.order_id)
            left = order.total_cents - order.refunded_cents
            if args.amount_cents > left:
                return ToolError("business", "amount_too_high",
                                 f"max {left} cents")
        day = (customer_id, self.today())
        if (customer_id is not None and not approved_by
                and needs_approval(args, self.per_day[day])):
            return ToolError("approval", "needs_approval",
                             "a person must approve this refund")
        if order is not None:
            order.refunded_cents += args.amount_cents
        self.per_day[day] += args.amount_cents
        return None

    def paid_today(self, customer_id):
        """Cents booked for this customer today (for policy checks)."""
        with self.lock:
            return self.per_day[(customer_id, self.today())]


def new_request_id():
    """Minted once, by our code, when a refund is first proposed."""
    return uuid.uuid4().hex[:12]


def make_key(conversation_id, order_id, request_id=""):
    # request_id: minted by our code, stored with the conversation and
    # reused by every retry. Never the reason or another model choice.
    return f"refund:{conversation_id}:{order_id}:{request_id}"
