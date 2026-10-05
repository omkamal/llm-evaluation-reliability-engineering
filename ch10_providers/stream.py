"""Consume a stream safely: buffer text, hold tool calls."""
import asyncio
import json
from dataclasses import dataclass, field

from ch10_providers.vtime import RealClock


class StreamStalled(Exception):
    pass


@dataclass
class StreamResult:
    status: str                     # "complete" or "incomplete"
    shown: list = field(default_factory=list)   # sentences shown
    tool_call: dict = None          # only from a complete stream
    partial_tool: str = ""          # a draft, never an instruction
    stop: str = None
    why: str = ""                   # cut | stalled | error


async def next_event(events, clock, idle):
    """The next event, unless the stream goes quiet for `idle` seconds."""
    nxt = asyncio.ensure_future(events.__anext__())
    timer = asyncio.ensure_future(clock.sleep(idle))
    try:
        await asyncio.wait({nxt, timer},
                           return_when=asyncio.FIRST_COMPLETED)
        if not nxt.done():
            raise StreamStalled()
        return nxt.result()
    finally:                       # leave no stray task behind
        timer.cancel()
        nxt.cancel()
        await asyncio.gather(nxt, timer, return_exceptions=True)


async def consume(events, show, clock=None, idle=10.0):
    clock = clock or RealClock()
    res, text, tool = StreamResult("incomplete"), "", ""
    try:
        while True:
            kind, value = await next_event(events, clock, idle)
            if kind == "text":
                text += value
                if text.endswith((".", "?", "!")):    # a safe boundary
                    show(text)
                    res.shown.append(text)
                    text = ""
            elif kind == "tool_delta":
                tool += value                     # hold it, never run it
            elif kind == "stop":
                res.stop = value
                break
            else:                                     # an error event
                res.why = "error"
                break
    except StopAsyncIteration:
        res.why = "cut"           # ended with no stop event
    except ConnectionError:
        res.why = "cut"
    except StreamStalled:
        res.why = "stalled"
    finally:
        await events.aclose()     # close the provider connection
    res.partial_tool = tool
    if res.stop is None:
        return res                    # a draft is not an answer
    if text:                          # the last words are safe now
        show(text)
        res.shown.append(text)
    try:
        res.tool_call = json.loads(tool) if tool else None
    except json.JSONDecodeError:
        res.why = "bad_json"          # a stop event, yet unusable JSON
        return res
    res.status, res.partial_tool = "complete", ""
    return res


def lenient(partial):
    """What a forgiving parser does with a cut tool call. Do not use."""
    return json.loads(partial + "}")


def recovery(result, *, effect_done=False, outcome_unknown=False):
    """After a bad ending, never re-run a step whose effect may exist."""
    if outcome_unknown:
        return "check", "ask by its key; never call again"
    if effect_done:
        return "confirm", "tell the customer from the record"
    if result.partial_tool:
        return "restart", "the tool never ran; ask again"
    if result.shown:
        return "resume", "continue after the last sentence"
    return "restart", "nothing shown; start again"
