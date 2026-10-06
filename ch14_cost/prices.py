"""Illustrative round prices, at the low end of the output-to-input
range (4 times); they equal one provider's older list prices, and are
not a quote for any model you use.

Two tiers, and the small one is cheaper per token on BOTH sides, as it
should be. Prices are dollars per million tokens: read your own list.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    inp: float          # dollars per 1M input tokens
    out: float          # dollars per 1M output tokens


PRICES = {"small": Price(0.40, 1.60), "frontier": Price(2.00, 8.00)}
CACHE_READ = 0.10       # a cached input token costs this share of one
CACHE_WRITE = 1.25      # writing a prefix into a cache costs this much
BATCH = 0.50            # a batch job is billed at this share


def call_usd(tier, fresh_in, out, *, cached_in=0, written=0, hidden=0):
    """Dollars for one call.

    fresh_in: input tokens at the normal rate; cached_in: read from a
    cache; written: written to one; hidden: reasoning tokens, which
    bill like output even though nobody sees them.
    """
    p = PRICES[tier]
    tokens_in = fresh_in + CACHE_READ * cached_in + CACHE_WRITE * written
    return (tokens_in * p.inp + (out + hidden) * p.out) / 1_000_000
