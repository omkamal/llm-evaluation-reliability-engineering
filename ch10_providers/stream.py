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
    why: str = ""                   # cut | stalled | error | length


async def next_event(events, clock, idle):
    """The next event, unless the stream goes quiet for `idle` seconds."""
    nxt = asyncio.create_task(events.__anext__())
    timer = asyncio.create_task(clock.sleep(idle))
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


def release(text, show, res):
    """Show held text if it ends a sentence; return what is still held."""
    if text.endswith((".", "?", "!")):
        show(text)
        res.shown.append(text)
        return ""
    return text


async def consume(events, show, clock=None, idle=10.0):
    clock = clock or RealClock()
    res, text, tool = StreamResult("incomplete"), "", ""
    try:
        while True:
            kind, value = await next_event(events, clock, idle)
            if kind == "text":
                if value[:1].isspace():   # "$15." + "00" is no full stop
                    text = release(text, show, res)
                text += value
            elif kind == "tool_delta":
                text = release(text, show, res)   # the text is over
                tool += value                     # hold it, never run it
            elif kind == "stop":
                res.stop = value
                break
            else:                                     # an error event
                res.why = "error"
                break
    except (StopAsyncIteration, ConnectionError):
        res.why = "cut"               # dropped, or ended with no stop
    except StreamStalled:
        res.why = "stalled"
    finally:
        await events.aclose()     # close the provider connection
    res.partial_tool = tool
    if res.stop not in ("end", "tool"):   # cut, or a token limit
        res.why = res.why or res.stop
        return res                        # a draft is not an answer
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
        return "replay", "same call and key; no new decision"
    if effect_done:
        return "confirm", "tell the customer from the record"
    if result.partial_tool:
        return "restart", "the tool never ran; ask again"
    if result.shown:
        return "resume", "continue after the last sentence"
    return "restart", "nothing shown; start again"
