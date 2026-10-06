"""Redaction at the edge, and the numbers that say tracing still works."""
import dataclasses
import json
from collections import defaultdict

EXPECTED = {"agent", "plan", "retrieval", "llm", "tool"}
PERSONAL = {"EMAIL", "PHONE", "CARD"}     # order ids stay: debugging needs them
IDENTIFIERS = {"order_id", "window"}      # tool arguments kept as they are


def _clean(value, redact):
    if isinstance(value, str):
        return redact(value)[0]
    if isinstance(value, list):
        return [_clean(v, redact) for v in value]
    return value


def clean_args(text, redact):
    """Tool arguments (JSON): identifiers stay, any other text is cleaned,
    so a ticket's description cannot carry an email into storage."""
    args = json.loads(text)
    return json.dumps({k: v if k in IDENTIFIERS else _clean(v, redact)
                       for k, v in args.items()}, sort_keys=True)


def redacting_export(redact):
    """A Tracer `export` step: store a cleaned COPY of each span. Free
    text lives in `.text` keys, tool arguments and event details;
    structured keys (ids, counts, tool names) hold none. It works on a
    copy because an exporter must: in OpenTelemetry an on_end hook gets a
    read-only span, so redacting there would change nothing."""
    def export(span):
        attrs = {k: clean_args(v, redact) if k == "relay.tool.args"
                 else _clean(v, redact) if k.endswith(".text") else v
                 for k, v in span.attributes.items()}
        events = [(when, name, {k: _clean(v, redact) for k, v in a.items()})
                  for when, name, a in span.events]
        return dataclasses.replace(span, attributes=attrs, events=events)
    return export


def personal_misses(spans, redact):
    """Stored spans in which the redactor still finds personal data. It
    sees only what the redactor can see: zero is not proof of clean."""
    missed = 0
    for sp in spans:
        values = list(sp.attributes.values()) + [
            v for _, _, attrs in sp.events for v in attrs.values()]
        found = set()
        for value in values:
            if isinstance(value, str):
                found |= set(redact(value)[1])
        missed += bool(found & PERSONAL)
    return missed


def orphans(spans):
    """Spans whose parent never arrived."""
    ids = {s.span_id for s in spans}
    return [s for s in spans if s.parent_id and s.parent_id not in ids]


def health(spans, redact):
    """The numbers of a trace health check, as a dict."""
    by_session = defaultdict(list)
    session_of = {s.trace_id: s.attributes["gen_ai.conversation.id"]
                  for s in spans if "gen_ai.conversation.id" in s.attributes}
    for s in spans:
        by_session[session_of.get(s.trace_id, s.trace_id)].append(s)
    complete = 0
    for group in by_session.values():
        one_trace = len({s.trace_id for s in group}) == 1
        kinds = {s.kind for s in group}
        complete += one_trace and EXPECTED <= kinds and not orphans(group)
    calls = [s for s in spans if s.kind == "llm"]
    covered = [s for s in calls if "gen_ai.usage.input_tokens" in s.attributes
               and "relay.cost_microusd" in s.attributes]
    return {"conversations": len(by_session), "spans": len(spans),
            "complete": complete / len(by_session),
            "orphan_rate": len(orphans(spans)) / len(spans),
            "attribute_coverage": len(covered) / len(calls),
            "personal_misses": personal_misses(spans, redact)}
