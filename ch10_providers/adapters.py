"""Adapters: each provider's dialect in, one common format out."""
from ch09_when_calls_fail.retry import RETRYABLE

STOPS = {"tool_use": "tool", "tool_calls": "tool", "end_turn": "end",
         "stop": "end", "max_tokens": "length", "length": "length"}
STATUS_A = {"overloaded": 529, "invalid_request": 400}
STATUS_B = {"rate_limited": 429, "invalid_request": 400}


def adapt_a(raw):
    """Provider A's event -> Relay's common (kind, value) event."""
    kind = raw["type"]
    if kind == "text_delta":
        return "text", raw["text"]
    if kind == "tool_json":
        return "tool_delta", raw["part"]
    if kind == "message_stop":
        return "stop", STOPS[raw["stop_reason"]]
    return "error", STATUS_A[raw["error"]]


def adapt_b(raw):
    """Provider B says the same things in different words."""
    if "error" in raw:
        return "error", STATUS_B[raw["error"]]
    choice = raw["choices"][0]
    if choice.get("finish_reason"):
        return "stop", STOPS[choice["finish_reason"]]
    delta = choice["delta"]
    if "content" in delta:
        return "text", delta["content"]
    return "tool_delta", delta["tool_args"]


def retryable(status):
    return status in RETRYABLE      # Chapter 9's classes, shared


async def adapted(raw_events, adapt):
    """Wrap a raw stream so the rest of Relay sees one format."""
    async for raw in raw_events:
        yield adapt(raw)
