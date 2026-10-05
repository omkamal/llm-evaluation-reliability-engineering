"""From trace to eval and back: graders read traces, traces collect scores,
and a bad trace becomes a new case."""
import json
from ch03_first_eval.cases import case


def calls_from_trace(spans):
    """Tool calls in the order they began: what a trajectory grader
    needs (Chapter 6 reads the same fields from a sandbox log)."""
    tools = sorted((s for s in spans if s.kind == "tool"),
                   key=lambda s: s.start)
    return [{"tool": s.attributes["gen_ai.tool.name"],
             "args": json.loads(s.attributes["relay.tool.args"]),
             "verified": s.attributes["relay.tool.verified"]}
            for s in tools]


def link_judge(tracer, graded, label, judge="judge_v2"):
    """Record a verdict as its own span that LINKS to the graded trace."""
    with tracer.span(f"chat {judge}", "llm", links=[graded.ctx]) as sp:
        sp.event("gen_ai.evaluation.result", **{
            "gen_ai.evaluation.name": "answer_quality",
            "gen_ai.evaluation.score.label": label})
    return sp


def failing_traces(spans):
    """Trace ids that a judge span linked to with a fail verdict."""
    bad = []
    for sp in spans:
        for _, name, attrs in sp.events:
            if (name == "gen_ai.evaluation.result"
                    and attrs["gen_ai.evaluation.score.label"] == "fail"):
                bad += [link.trace_id for link in sp.links]
    return bad


def trace_to_case(root, topic, expected, forbidden, cid):
    """A failing trace becomes a Chapter 3 case: the customer's words come
    from the trace, the criteria from the person who read it."""
    question = root.attributes["relay.request.text"]
    return {**case(cid, topic, question, [expected], [forbidden]),
            "source": "trace", "trace_id": root.trace_id}
