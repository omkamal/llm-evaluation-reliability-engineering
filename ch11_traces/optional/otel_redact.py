"""Redaction with the real OpenTelemetry SDK (optional; not run by CI).

An on_end hook cannot redact: the SDK hands it a read-only span, so the
email is exported untouched. A wrapper around the exporter can: it sends
cleaned copies. Run once on 5 October 2026 with opentelemetry-sdk 1.45.0
and Python 3.12.3, in a throwaway virtualenv:
    pip install "opentelemetry-sdk==1.45.0"
    python ch11_traces/optional/otel_redact.py     (from code/: uses Ch 7)
It printed:
    on_end hook: 'mappingproxy' object does not support item assignment
    on_end:  {"order_id": "ORD-004829", "description": "lost; anna.kel...
    wrapper: {"description": "lost; <EMAIL_1>", "order_id": "ORD-004829"}
    event:   reply to <EMAIL_1>
"""
import json
import sys
from pathlib import Path

from opentelemetry.sdk.trace import (Event, ReadableSpan, SpanProcessor,
                                     TracerProvider)
from opentelemetry.sdk.trace.export import (SimpleSpanProcessor,
                                            SpanExporter)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ch07_datasets.redact import redact            # noqa: E402

IDENTIFIERS = {"order_id", "window"}               # these stay readable
ARGS = "gen_ai.tool.call.arguments"


def clean(key, value):
    """Free text: `.text` keys, tool arguments, event details."""
    if not isinstance(value, str):
        return value
    if key == ARGS:
        args = json.loads(value)
        return json.dumps({k: v if k in IDENTIFIERS
                           or not isinstance(v, str) else redact(v)[0]
                           for k, v in args.items()}, sort_keys=True)
    return redact(value)[0] if key.endswith(".text") else value


class OnEndRedactor(SpanProcessor):
    """The tempting way, which fails: the ended span is read-only."""

    def on_end(self, span):
        try:
            for key, value in span.attributes.items():
                span.attributes[key] = clean(key, value)
        except TypeError as why:
            print("on_end hook:", why)


class RedactingExporter(SpanExporter):
    """Wrap any exporter; what leaves the process is the cleaned copy."""

    def __init__(self, inner):
        self.inner = inner

    def export(self, spans):
        return self.inner.export([self.copy(s) for s in spans])

    @staticmethod
    def copy(s):
        attrs = {k: clean(k, v) for k, v in s.attributes.items()}
        events = [Event(e.name, {k: redact(v)[0] if isinstance(v, str)
                                 else v for k, v in e.attributes.items()},
                        e.timestamp) for e in s.events]
        return ReadableSpan(
            s.name, s.context, s.parent, s.resource, attrs, events,
            s.links, s.kind, status=s.status, start_time=s.start_time,
            end_time=s.end_time,
            instrumentation_scope=s.instrumentation_scope)

    def shutdown(self):
        self.inner.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self.inner.force_flush(timeout_millis)


def one_ticket(processors):
    """Record one tool span whose arguments hold an email."""
    provider = TracerProvider()
    for processor in processors:
        provider.add_span_processor(processor)
    tracer = provider.get_tracer("relay")
    with tracer.start_as_current_span("execute_tool create_ticket") as sp:
        sp.set_attribute(ARGS, json.dumps(
            {"order_id": "ORD-004829",
             "description": "lost; anna.keller@example.com"}))
        sp.add_event("note",
                     {"detail": "reply to anna.keller@example.com"})


hooked, wrapped = InMemorySpanExporter(), InMemorySpanExporter()
one_ticket([OnEndRedactor(), SimpleSpanProcessor(hooked)])
one_ticket([SimpleSpanProcessor(RedactingExporter(wrapped))])
print("on_end: ", hooked.get_finished_spans()[0].attributes[ARGS])
stored = wrapped.get_finished_spans()[0]
print("wrapper:", stored.attributes[ARGS])
print("event:  ", stored.events[0].attributes["detail"])
