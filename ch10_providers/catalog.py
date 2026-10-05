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


def text_only(req):
    """The same request with no tool calls: what tier 2 can serve."""
    return Request(req.region, req.tokens, False, req.blocked, req.lane)


def make_catalog():
    both = frozenset({"global", "eu"})
    return [
        Provider("Provider A", frozenset({"global"}), 200_000, True,
                 6.0, limit=120),
        Provider("Provider B", both, 128_000, True, 8.0),
        Provider("Provider B small", both, 32_000, False, 1.0),
    ]
