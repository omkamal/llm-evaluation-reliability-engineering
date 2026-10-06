"""Providers, requests and the hard filters: filter first, rank second."""
from dataclasses import dataclass


@dataclass
class Provider:
    name: str
    regions: frozenset       # where it may process data
    max_context: int         # tokens
    tools: bool              # can it call tools?
    cost: float              # dollars per 1M tokens
    limit: int = 40          # most calls in flight at once
    in_flight: int = 0
    cleared: bool = True     # has its prompt passed Relay's eval set?
    held: int = 0            # slots only EU chats may use
    global_calls: int = 0    # calls in flight from global traffic

    @property
    def free_slots(self):
        return self.limit - self.in_flight


@dataclass(frozen=True)
class Request:
    region: str              # "eu" or "global": where the data may go
    tokens: int
    needs_tools: bool
    blocked: frozenset = frozenset()   # providers a contract rules out
    lane: str = "chat"


class NoEligibleProvider(Exception):
    pass


def rejections(provider, req):
    """Why this provider may not serve this request (empty: it may)."""
    why = []
    if req.region not in provider.regions:
        why.append("residency")
    if not provider.cleared:
        why.append("capability")
    if req.tokens > provider.max_context:
        why.append("context")
    if req.needs_tools and not provider.tools:
        why.append("tools")
    if provider.name in req.blocked:
        why.append("policy")
    return why


def eligible(catalog, req):
    return [p for p in catalog if not rejections(p, req)]


def has_room(provider, req):
    """A free slot, and global traffic stays out of the held ones."""
    if provider.free_slots <= 0:
        return False
    spill_cap = provider.limit - provider.held
    return req.region != "global" or provider.global_calls < spill_cap


def available(catalog, req, tripped=()):
    """Eligible, breaker not open, and a slot this request may use."""
    return [p for p in eligible(catalog, req)
            if p.name not in tripped and has_room(p, req)]


def take_slot(provider, req):
    """Count a call in flight (the gateway does this per request)."""
    provider.in_flight += 1
    if req.region == "global":
        provider.global_calls += 1


def text_only(req):
    """The same request with no tool calls: what tier 2 can serve."""
    return Request(req.region, req.tokens, False, req.blocked, req.lane)


def make_catalog():
    both = frozenset({"global", "eu"})
    return [
        Provider("Provider A", frozenset({"global"}), 200_000, True,
                 6.0, limit=120),
        # each EU model holds 28 of its 40 slots for EU chats: their
        # usual 20 plus a fifth of the limit; global spill-over gets 12
        Provider("Provider B", both, 128_000, True, 8.0, held=28),
        Provider("Provider B small", both, 32_000, False, 1.0, held=28),
    ]
