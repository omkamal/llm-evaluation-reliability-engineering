"""Small levers: batch, compress the context, control the output."""
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


def saved_per_call(before, after, tier="frontier"):
    """Dollars of input saved on every later call of the session."""
    return call_usd(tier, before - after, 0)


def reply_usd(text, tier="frontier"):
    """What the reply itself costs: output is the dear side."""
    return count_tokens(text) * PRICES[tier].out / 1_000_000
