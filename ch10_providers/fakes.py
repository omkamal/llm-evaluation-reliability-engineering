"""Scripted provider streams that die, stall or finish. Illustrative."""
import json

FULL = [
    ("text", "I can refund order ORD-004830."),
    ("text", " The refund is"),
    ("text", " $15.00."),
    ("tool_delta", '{"order_id": "ORD-004830", '),
    ("tool_delta", '"reason": '),
    ("tool_delta", '"damaged", '),
    ("tool_delta", '"amount_cents": 15'),
    ("tool_delta", "00"),
    ("tool_delta", "}"),
    ("stop", "tool"),
]
GOOD_CALL = {"order_id": "ORD-004830", "reason": "damaged",
             "amount_cents": 1500}
assert json.loads("".join(v for k, v in FULL if k == "tool_delta")) \
    == GOOD_CALL


async def stream(events, clock, *, cut_after=None, stall_after=None,
                 gap=0.05):
    """Yield events with a gap between them; die or go quiet on cue."""
    for n, event in enumerate(events):
        if cut_after is not None and n == cut_after:
            raise ConnectionError("stream cut")
        if stall_after is not None and n == stall_after:
            await clock.sleep(10**6)         # connection open, no data
        await clock.sleep(gap)
        yield event


def to_a(event):
    """The same event as Provider A would write it."""
    kind, value = event
    if kind == "text":
        return {"type": "text_delta", "text": value}
    if kind == "tool_delta":
        return {"type": "tool_json", "part": value}
    return {"type": "message_stop", "stop_reason": "tool_use"}


def to_b(event):
    """The same event as Provider B would write it."""
    kind, value = event
    if kind == "text":
        return {"choices": [{"delta": {"content": value}}]}
    if kind == "tool_delta":
        return {"choices": [{"delta": {"tool_args": value}}]}
    return {"choices": [{"finish_reason": "tool_calls"}]}
