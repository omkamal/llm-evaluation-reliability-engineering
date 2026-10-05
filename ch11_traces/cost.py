"""What telemetry costs to keep. Every input is a stated assumption:
change them and rerun."""
import json

BYTES_PER_TOKEN = 4          # a rough rule of thumb for English text


def structure_bytes(spans):
    """Size of one run's spans written as JSON, attributes and events
    included, message text excluded. A real backend stores a compact
    binary form but adds indexes, so measure your own."""
    return sum(len(json.dumps({"name": s.name, "kind": s.kind,
                               "trace": s.trace_id, "span": s.span_id,
                               "parent": s.parent_id, "start": s.start,
                               "end": s.end, "attrs": s.attributes,
                               "events": s.events, "status": s.status}))
               for s in spans)


def text_bytes(spans):
    """Size of the prompts and replies if their text were stored too."""
    tokens = sum(s.attributes.get("gen_ai.usage.input_tokens", 0)
                 + s.attributes.get("gen_ai.usage.output_tokens", 0)
                 for s in spans)
    return tokens * BYTES_PER_TOKEN


def steady_gb(conversations, share, bytes_each, days):
    """Gigabytes held at steady state: a month's volume times the months
    it is kept."""
    return conversations * share * bytes_each * days / 30 / 1e9
