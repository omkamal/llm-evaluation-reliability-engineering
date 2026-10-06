"""An LLM call is a metered function: tokens in, tokens out, a price and a clock.
A toy stands in for the model so the numbers are exact. Prices are illustrative."""
import json
import re
from dataclasses import dataclass

PRICE_IN, PRICE_OUT = 1.00, 5.00   # $ per million tokens (illustrative)

TOKEN = re.compile(r"\w+|[^\w\s]")     # toy tokens: words and punctuation


def count_tokens(text):
    """A toy tokenizer: words and punctuation. Real tokenizers differ."""
    return len(TOKEN.findall(text))


@dataclass
class Completion:
    text: str
    finish_reason: str                 # "stop" = finished; "length" = cut off
    input_tokens: int
    output_tokens: int
    latency_ms: int


def complete(prompt, *, answer, max_tokens):
    """Pretend to answer; cut off after max_tokens tokens."""
    tokens = list(TOKEN.finditer(answer))
    kept = tokens[:max_tokens]
    finish = "stop" if len(kept) == len(tokens) else "length"
    out = answer[:kept[-1].end()] if kept else ""
    return Completion(out, finish, count_tokens(prompt), len(kept),
                      latency_ms=300 + 20 * len(kept))


def cost_microusd(c):
    """Whole millionths of a dollar: price per million tokens is micro-dollars per token."""
    return round(c.input_tokens * PRICE_IN + c.output_tokens * PRICE_OUT)


def log_line(request_id, model, c):
    """Flight recorder lite: one JSON line per call."""
    return json.dumps({"request_id": request_id, "model": model,
                       "input_tokens": c.input_tokens,
                       "output_tokens": c.output_tokens,
                       "finish_reason": c.finish_reason,
                       "latency_ms": c.latency_ms,
                       "cost_microusd": cost_microusd(c)})
