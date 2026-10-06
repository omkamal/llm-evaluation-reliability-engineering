"""Adapters: each provider's dialect in, one common format out."""
from ch09_when_calls_fail.retry import RETRYABLE

STOPS = {"tool_use": "tool", "tool_calls": "tool", "end_turn": "end",
         "stop": "end", "max_tokens": "length", "length": "length"}
# a spend cap is a 429 on the wire with no Retry-After: it fails until
# access resumes, so it gets a status Chapter 9 never retries (fail over)
STATUS_A = {"overloaded": 529, "invalid_request": 400, "spend_cap": 402}
STATUS_B = {"rate_limited": 429, "invalid_request": 400, "spend_cap": 402}
UNKNOWN_ERROR = 500         # an error code we have never seen: transient


def adapt_a(raw):
    """Provider A's event -> Relay's common (kind, value) event."""
    kind = raw["type"]
    if kind == "text_delta":
        return "text", raw["text"]
    if kind == "tool_json":
        return "tool_delta", raw["part"]
    if kind == "message_stop":
        reason = raw["stop_reason"]
        return "stop", STOPS.get(reason, reason)    # e.g. "refusal"
    if kind == "error":
        return "error", STATUS_A.get(raw["error"], UNKNOWN_ERROR)
    return None              # a ping or a new event type: drop it


def adapt_b(raw):
    """Provider B says the same things in different words."""
    if "error" in raw:
        return "error", STATUS_B.get(raw["error"], UNKNOWN_ERROR)
    choice = raw["choices"][0]
    if choice.get("finish_reason"):
        reason = choice["finish_reason"]
        return "stop", STOPS.get(reason, reason)
    delta = choice["delta"]
    if "content" in delta:
        return "text", delta["content"]
    return "tool_delta", delta["tool_args"]


def retryable(status):
    return status in RETRYABLE      # Chapter 9's classes, shared


async def adapted(raw_events, adapt):
    """Wrap a raw stream so the rest of Relay sees one format.

    Keep-alives are dropped here, so they never reset the idle timer:
    they prove the socket is open, not that the model is writing."""
    async for raw in raw_events:
        event = adapt(raw)
        if event is not None:
            yield event
