"""One request through the incident: Chapter 9's defences, then ours."""
from collections import Counter

from ch02_trust_outputs.idem import Payments, RefundService, make_key
from ch02_trust_outputs.refund import ToolError, validate_refund_args
from ch09_when_calls_fail.breaker import CircuitBreaker
from ch09_when_calls_fail.budget import RetryBudget
from ch09_when_calls_fail.quota import QuotaManager
from ch10_providers.adapters import adapt_b, adapted
from ch10_providers.catalog import NoEligibleProvider, make_catalog
from ch10_providers.fakes import FULL, stream, to_b
from ch10_providers.health import HealthWindow
from ch10_providers.ranking import Signals, route
from ch10_providers.stream import consume, recovery
from ch10_providers.tiers import choose_tier


class World:
    """The afternoon of the outage: A is down, B is busy but healthy."""

    def __init__(self, clock):
        self.clock = clock
        self.catalog = make_catalog()
        self.health = {p.name: HealthWindow(clock) for p in self.catalog}
        self.breakers = {p.name: CircuitBreaker(clock=clock)
                         for p in self.catalog}
        self.quota = QuotaManager()
        self.retries = RetryBudget()
        self.payments = Payments()
        self.refunds = RefundService(self.payments)
        self.streams = [7, None]       # B's first stream dies at 70%
        self.calls = Counter()         # calls made, by provider
        self.violations = 0            # EU data sent outside the EU
        a, b, small = self.catalog
        a.in_flight, b.in_flight = 80, 20
        self._warm(a, ok=55, bad=45, ttft=4.0)
        self._warm(b, ok=99, bad=1, ttft=1.5)
        self._warm(small, ok=99, bad=1, ttft=0.8)
        for _ in range(5):
            self.breakers[a.name].record(False)       # A is down

    def _warm(self, p, ok, bad, ttft):
        for i in range(ok + bad):
            self.health[p.name].record(i < ok, ttft if i < ok else None)

    def signals(self):
        return {p.name: Signals(self.health[p.name].success(),
                                self.health[p.name].ttft_p95(),
                                p.free_slots / p.limit,
                                self.breakers[p.name].state)
                for p in self.catalog}


async def serve(w, req, user, conversation, say):
    say(f"quota: {w.quota.admit('interactive', req.tokens)}")
    try:
        provider = route(w.catalog, req, w.signals())
    except NoEligibleProvider:
        down = {n for n, b in w.breakers.items() if b.state == "open"}
        say(f"no eligible provider with room: tier "
            f"{choose_tier(w.catalog, req, tripped=down)}")
        return None
    say(f"route: {provider.name}")
    if req.region not in provider.regions:
        w.violations += 1              # must stay at zero
    w.retries.record_request()
    for attempt in (1, 2):
        shown = []
        w.calls[provider.name] += 1
        raw = stream([to_b(e) for e in FULL], w.clock,
                     cut_after=w.streams.pop(0))
        res = await consume(adapted(raw, adapt_b), shown.append, w.clock)
        w.breakers[provider.name].record(res.status == "complete")
        if res.status == "complete":
            break
        action, why = recovery(res)
        say(f"attempt {attempt}: stream {res.why}, {action}: {why}")
        if attempt == 2:
            say("backup failed twice: hand off to a human")
            return None
        if not w.retries.allow_retry():
            say("retry budget empty: hand off to a human")
            return None
    call = validate_refund_args(res.tool_call, user)
    if isinstance(call, ToolError):
        say(f"tool call rejected: {call.layer}")
        return None
    key = make_key(conversation, call.order_id)
    done = w.refunds.issue_refund(call, key)
    cents = done["amount_cents"]
    say(f"attempt {attempt}: complete, refund {cents} cents")
    return done
