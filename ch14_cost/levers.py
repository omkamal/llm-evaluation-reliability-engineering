"""Small levers: batch, compress the context, control the output."""
from math import ceil

from ch01_anatomy.call import count_tokens
from ch11_traces.context import trim_oldest_first
from ch14_cost.prices import BATCH, PRICES, call_usd

SUMMARY_TOKENS = 200      # room the Summarizer's note needs


def lane(deadline_hours):
    """Nobody waiting for the answer? Send it through the batch lane."""
    return "batch" if deadline_hours >= 4 else "interactive"


def batch_usd(usd):
    return usd * BATCH


def compress(turns, budget, summarizer):
    """Keep the newest turns, fold the rest into the Summarizer's note.

    Chapter 11's trim; `summarizer` is a lossy or a careful one.
    """
    kept, dropped = trim_oldest_first(turns, budget - SUMMARY_TOKENS)
    return [kept[0], summarizer(dropped)] + kept[1:]


def tokens(turns):
    return sum(t.tokens for t in turns)


def saved_per_call(before, after, tier="frontier", cached=False):
    """Dollars of input saved on every later call of the session.

    With the prompt cache on, the trimmed tokens were being read at a
    tenth of the price, so the saving is a tenth too.
    """
    if cached:
        return call_usd(tier, 0, 0, cached_in=before - after)
    return call_usd(tier, before - after, 0)


def payback_calls(turns, new, tier="frontier", summary_tier="small"):
    """Later calls a CACHED session needs before a summary pays off.

    Paid once: the Summarizer reads what was dropped (on the small
    tier, as in Chapter 11), and everything after the system prompt
    is written to the cache again instead of being read from it.
    """
    before, after = tokens(turns), tokens(new)
    dropped = before - (after - SUMMARY_TOKENS)
    rewritten = after - turns[0].tokens
    once = (call_usd(summary_tier, dropped, SUMMARY_TOKENS)
            + call_usd(tier, 0, 0, written=rewritten)
            - call_usd(tier, 0, 0, cached_in=rewritten))
    return ceil(once / saved_per_call(before, after, tier, cached=True))


def reply_usd(text, tier="frontier"):
    """What the reply itself costs: output is the expensive side."""
    return count_tokens(text) * PRICES[tier].out / 1_000_000
