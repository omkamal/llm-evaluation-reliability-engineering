"""An LLM call is a metered function: tokens in, tokens out, a price and a clock.
A toy stands in for the model so the numbers are exact. Prices are illustrative."""
import json
import re
from dataclasses import dataclass

PRICE_IN, PRICE_OUT = 1.00, 5.00       # dollars per million tokens (illustrative)


def count_tokens(text):
    """A toy tokenizer: words and punctuation. Real tokenizers differ."""
    return len(re.findall(r"\w+|[^\w\s]", text))


@dataclass
class Completion:
    text: str
    finish_reason: str                 # "stop" = finished; "length" = cut off
    input_tokens: int
    output_tokens: int
    latency_ms: int


def complete(prompt, *, answer, max_tokens):
    """Pretend to answer; cut off at max_tokens."""
    words = re.findall(r"\S+", answer)
    kept = words[:max_tokens]
    finish = "stop" if len(kept) == len(words) else "length"
    out = " ".join(kept)
    return Completion(out, finish, count_tokens(prompt), count_tokens(out),
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
