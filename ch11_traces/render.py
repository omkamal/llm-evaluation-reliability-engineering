"""Print a trace as an indented tree, and one span in full."""
import json
from collections import defaultdict


def _detail(span):
    a = span.attributes
    if span.kind == "llm":
        if "gen_ai.usage.input_tokens" not in a:
            return "no usage recorded"
        cost = a.get("relay.cost_microusd", 0) / 1_000_000
        return (f"{a['gen_ai.usage.input_tokens']:,} in / "
                f"{a['gen_ai.usage.output_tokens']:,} out, ${cost:.4f}")
    if span.kind == "retrieval":
        return (f"{a['relay.retrieval.status']}, index "
                f"{a['relay.index.version']}, "
                f"{len(a['relay.retrieval.chunks'])} chunks")
    if span.kind == "tool":
        return f"tier {a['relay.tool.tier']}"
    if span.kind == "state":
        lost = ", ".join(a["relay.context.fields_lost"]) or "nothing"
        return (f"{a['relay.context.tokens_before']:,} -> "
                f"{a['relay.context.tokens_after']:,} tokens, lost {lost}")
    return ""


def _failure(span):
    if span.status != "error":
        return ""
    bad = span.events[-1][2]
    return f"  ERROR {bad['type']}: {bad['message']}"


def _event_text(name, attrs):
    if name == "exception":
        return f"! exception: {attrs['type']}: {attrs['message']}"
    values = list(attrs.values())
    body = values[0] if len(values) == 1 else ", ".join(
        f"{k}={v}" for k, v in attrs.items())
    return f"! {name}: {body}"


def render_tree(spans, collapse=True):
    """Lines for every trace in `spans`, one indented tree per trace."""
    by_trace = defaultdict(list)
    for position, sp in enumerate(spans):
        by_trace[sp.trace_id].append((position, sp))
    lines = []
    for trace_id, items in by_trace.items():
        ids = {sp.span_id for _, sp in items}
        kids = defaultdict(list)
        for position, sp in sorted(items, key=lambda i: (i[1].start, i[0])):
            parent = sp.parent_id if sp.parent_id in ids else None
            kids[parent].append(sp)
        session = next((sp.attributes["gen_ai.conversation.id"]
                        for _, sp in items
                        if "gen_ai.conversation.id" in sp.attributes), "-")
        lines.append(f"trace {trace_id[:8]}  {session}  "
                     f"{len(items)} spans")

        def walk(sp, depth):
            marker = "? " if sp.parent_id and sp.parent_id not in ids else ""
            flag = "  ERROR" if sp.status == "error" else ""
            lines.append(f"{'  ' * depth}{marker}{sp.name}  "
                         f"{sp.duration:.2f}s  {_detail(sp)}{flag}".rstrip())
            pad = "  " * (depth + 1)
            rows = [(when, 0, f"{pad}{_event_text(name, attrs)}")
                    for when, name, attrs in sp.events]
            for run in _runs(kids[sp.span_id], kids, collapse):
                if len(run) == 1:
                    rows.append((run[0].start, 1, run[0]))
                else:
                    total = sum(c.duration for c in run)
                    why = _failure(run[0])
                    rows.append((run[0].start, 1, f"{pad}{run[0].name} "
                                 f"x{len(run)}  {total:.2f}s{why}"))
            for _, _, row in sorted(rows, key=lambda r: r[:2]):
                if isinstance(row, str):
                    lines.append(row)
                else:
                    walk(row, depth + 1)

        for root in kids[None]:
            walk(root, 0)
    return lines


def _runs(children, kids, collapse):
    """Group neighbours that repeat one another exactly."""
    runs = []
    for child in children:
        if (collapse and runs and not kids[child.span_id]
                and not kids[runs[-1][0].span_id]
                and _key(runs[-1][0]) == _key(child)):
            runs[-1].append(child)
        else:
            runs.append([child])
    return runs


def _key(span):
    """What must match for two siblings to count as one repeated step."""
    events = tuple((name, tuple(attrs.items()))
                   for _, name, attrs in span.events)
    return span.name, span.kind, span.status, events


def describe(span):
    """Every attribute and event of one span, one per line."""
    lines = [f"{span.name}  ({span.kind}, {span.status})"]
    for key, value in span.attributes.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f"  {key}:")
            lines += [f"    - {json.dumps(item)}" for item in value]
            continue
        shown = value if isinstance(value, str) else json.dumps(value)
        lines.append(f"  {key}: {shown}")
    for when, name, attrs in span.events:
        lines.append(f"  event {name}: {json.dumps(attrs)}")
    return lines


def log_line(span):
    """Chapter 1's flight-recorder line, grown: the same vital signs plus
    the three ids that tie it to a tree."""
    a = span.attributes
    return json.dumps({"trace": span.trace_id[:8], "span": span.span_id[:8],
                       "parent": (span.parent_id or "-")[:8],
                       "model": a["gen_ai.request.model"],
                       "input_tokens": a["gen_ai.usage.input_tokens"],
                       "output_tokens": a["gen_ai.usage.output_tokens"],
                       "finish_reason": a["gen_ai.response.finish_reasons"][0],
                       "latency_ms": round(span.duration * 1000),
                       "cost_microusd": a["relay.cost_microusd"]})
