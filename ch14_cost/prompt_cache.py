"""A prefix (prompt) cache: an identical start of the prompt is reused.

This is a model of the idea, not of any provider. A prompt is a list of
blocks; the cache remembers every prefix it has seen for a while.
"""
from ch14_cost.prices import CACHE_READ, CACHE_WRITE


class PrefixCache:
    def __init__(self, clock, ttl=300.0, min_tokens=1024):
        self.clock, self.ttl, self.min_tokens = clock, ttl, min_tokens
        self.seen = {}               # prefix of blocks -> expires at

    def send(self, blocks):
        """blocks: [(text, tokens)]. Returns (cached, written, fresh)."""
        total = sum(n for _, n in blocks)
        if total < self.min_tokens:
            return 0, 0, total       # too short to cache: pay full price
        now, cached, size = self.clock.now(), 0, 0
        for i, (_, n) in enumerate(blocks):
            size += n
            prefix = tuple(t for t, _ in blocks[:i + 1])
            if self.seen.get(prefix, -1.0) > now:
                cached = size        # the longest prefix still alive
        for i in range(len(blocks)):         # every prefix is (re)stamped
            prefix = tuple(t for t, _ in blocks[:i + 1])
            self.seen[prefix] = now + self.ttl
        return cached, total - cached, 0     # the rest is written


def equivalent_tokens(cached, written, fresh):
    """Input tokens at the normal price that the call is worth."""
    return CACHE_READ * cached + CACHE_WRITE * written + fresh


def break_even_uses():
    """Smallest number of uses inside the TTL for which writing pays."""
    uses = 1
    while CACHE_WRITE + CACHE_READ * (uses - 1) >= uses:
        uses += 1
    return uses
