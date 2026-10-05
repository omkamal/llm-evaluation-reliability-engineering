"""A tiny tracer: spans, context, events, errors. Standard library only.

The clock and the id generator are injected, so a run prints the same
tree every time. A real SDK (OpenTelemetry, see optional/) does the same
job with more options."""
import contextvars
import random
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import NamedTuple, Optional

SPAN_KINDS = ("agent", "plan", "retrieval", "llm", "tool", "state")


class Context(NamedTuple):
    """What must travel with a handoff: which trace, which open step."""
    trace_id: str            # 32 hex characters: one run, start to end
    span_id: str             # 16 hex characters: the step open right now
    sampled: bool = True     # was this trace chosen for recording?


class IdGenerator:
    """Seeded ids. A real SDK draws them at random from the system."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def _hex(self, bits):
        while True:
            number = self.rng.getrandbits(bits)
            if number:                  # all zeros is not a valid id
                return f"{number:0{bits // 4}x}"

    def trace_id(self):
        return self._hex(128)

    def span_id(self):
        return self._hex(64)


@dataclass
class Span:
    name: str
    kind: str
    ctx: Context
    parent_id: Optional[str]
    start: float
    clock: object = field(default=None, repr=False)
    end: Optional[float] = None
    attributes: dict = field(default_factory=dict)
    events: list = field(default_factory=list)   # (time, name, attrs)
    links: list = field(default_factory=list)    # Contexts of other spans
    status: str = "ok"                           # "ok" or "error"

    @property
    def trace_id(self):
        return self.ctx.trace_id

    @property
    def span_id(self):
        return self.ctx.span_id

    @property
    def duration(self):
        return (self.end or self.clock.now()) - self.start

    def set(self, attrs):
        self.attributes.update(attrs)

    def event(self, name, **attrs):
        self.events.append((self.clock.now(), name, attrs))


_current = contextvars.ContextVar("current_context", default=None)


def current():
    """The Context of the open span, or None outside any span."""
    return _current.get()


class Tracer:
    def __init__(self, clock, ids=None, sampler=None, on_end=None):
        self.clock = clock
        self.ids = ids or IdGenerator()
        self.sampler = sampler or (lambda trace_id: True)
        self.on_end = on_end or (lambda span: None)   # edge hook
        self.finished = []

    @contextmanager
    def span(self, name, kind, *, context=None, links=(), attrs=None):
        parent = context or current()        # an explicit context wins
        if parent is None:                   # a new root starts a trace
            trace_id = self.ids.trace_id()
            ctx = Context(trace_id, self.ids.span_id(),
                          self.sampler(trace_id))
        else:                                # children inherit the choice
            ctx = Context(parent.trace_id, self.ids.span_id(),
                          parent.sampled)
        sp = Span(name, kind, ctx, parent.span_id if parent else None,
                  self.clock.now(), clock=self.clock, links=list(links))
        sp.set(attrs or {})
        token = _current.set(ctx)
        try:
            yield sp
        except Exception as exc:             # an error is data
            sp.status = "error"
            sp.event("exception", type=type(exc).__name__,
                     message=str(exc))
            raise
        finally:
            _current.reset(token)
            sp.end = self.clock.now()
            if ctx.sampled:
                self.on_end(sp)
                self.finished.append(sp)


TRACEPARENT = re.compile(
    r"([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})")


def inject(carrier, ctx=None):
    """Write the open span's context into message headers."""
    ctx = ctx or current()
    if ctx is not None:
        flags = "01" if ctx.sampled else "00"
        carrier["traceparent"] = (
            f"00-{ctx.trace_id}-{ctx.span_id}-{flags}")
    return carrier


def extract(carrier):
    """Read a Context from headers; None if missing or malformed."""
    found = TRACEPARENT.fullmatch(carrier.get("traceparent", ""))
    if not found:
        return None
    version, trace_id, span_id, flags = found.groups()
    if version == "ff" or not int(trace_id, 16) or not int(span_id, 16):
        return None                          # forbidden or all-zero ids
    return Context(trace_id, span_id, bool(int(flags, 16) & 1))
