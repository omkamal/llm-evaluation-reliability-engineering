"""Rank the eligible providers: health first, then speed, then cost."""
from dataclasses import dataclass

from ch10_providers.catalog import NoEligibleProvider, eligible
from ch10_providers.health import SLOW

W_HEALTH, W_SPEED, W_THRIFT = 0.6, 0.3, 0.1
PRICEY = 20.0       # dollars per 1M tokens that score zero for thrift
HEADROOM_OK = 0.2   # below this share of free slots, health fades


@dataclass
class Signals:
    success: float          # share of calls that worked, last 5 minutes
    ttft: float             # p95 seconds to first token
    headroom: float         # share of the concurrency limit still free
    breaker: str = "closed"


def health(s):
    room = min(1.0, s.headroom / HEADROOM_OK)
    return s.success * room


def score(provider, s):
    speed = 1 - min(s.ttft, SLOW) / SLOW
    thrift = 1 - min(provider.cost, PRICEY) / PRICEY
    return W_HEALTH * health(s) + W_SPEED * speed + W_THRIFT * thrift


def rank(catalog, req, signals):
    """Eligible providers with room, best first; ties are settled."""
    usable = [p for p in eligible(catalog, req)
              if p.free_slots > 0 and signals[p.name].breaker != "open"]
    # equal to 2 decimals counts as a tie: cheaper wins, then the name
    return sorted(usable, key=lambda p: (
        -round(score(p, signals[p.name]), 2), p.cost, p.name))


def route(catalog, req, signals):
    ranked = rank(catalog, req, signals)
    if not ranked:
        raise NoEligibleProvider(req.region)   # never relax a hard filter
    return ranked[0]
