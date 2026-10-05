"""The same idea with the real OpenTelemetry SDK (optional; not run by CI).

Setup, in a throwaway virtualenv:  pip install "opentelemetry-sdk==1.45.0"
Run:  python otel_demo.py
"""
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter)

exporter = InMemorySpanExporter()           # keep spans in memory
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("relay")

message = {"headers": {}}                   # what travels on the queue
with tracer.start_as_current_span("invoke_agent Planner") as planner:
    planner.set_attributes({"gen_ai.operation.name": "invoke_agent",
                            "gen_ai.agent.name": "Planner",
                            "gen_ai.conversation.id": "conv-0412"})
    with tracer.start_as_current_span("chat a-large-v2") as call:
        call.set_attributes({"gen_ai.operation.name": "chat",
                             "gen_ai.usage.input_tokens": 3100,
                             "gen_ai.usage.output_tokens": 210})
        call.add_event("retry", {"detail": "attempt 1: 429"})
    inject(message["headers"])              # writes the traceparent

for header in (message["headers"], {}):     # header kept, then dropped
    context = extract(header)               # empty if no header
    with tracer.start_as_current_span("invoke_agent Researcher",
                                      context=context):
        pass

spans = exporter.get_finished_spans()
names = {s.context.span_id: s.name for s in spans}
print("traceparent:", message["headers"]["traceparent"])
for s in sorted(spans, key=lambda s: s.start_time):
    parent = names.get(s.parent.span_id) if s.parent else "(root)"
    print(f"{s.name:<26} parent: {parent}")
print("traces:", len({s.context.trace_id for s in spans}))
