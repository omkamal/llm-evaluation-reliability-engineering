"""Redaction at the edge, and the numbers that say tracing still works."""
from collections import defaultdict

EXPECTED = {"agent", "plan", "retrieval", "llm", "tool"}
PERSONAL = {"EMAIL", "PHONE", "CARD"}     # order ids stay: debugging needs them


def _clean(value, redact):
    if isinstance(value, str):
        return redact(value)[0]
    if isinstance(value, list):
        return [_clean(v, redact) for v in value]
    return value


def edge_hook(redact):
    """A Tracer `on_end` hook: clean the free-text keys before storage.
    Structured keys (ids, counts, tool names) never hold free text."""
    def hook(span):
        for key, value in span.attributes.items():
            if key.endswith(".text"):
                span.attributes[key] = _clean(value, redact)
    return hook


def personal_misses(spans, redact):
    """Stored spans in which the redactor still finds personal data."""
    missed = 0
    for sp in spans:
        found = set()
        for value in sp.attributes.values():
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
