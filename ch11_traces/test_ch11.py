"""Tests for Chapter 11: every behaviour the chapter claims, and each
worked example it prints."""
import asyncio
import contextvars
import json

import pytest

from ch03_first_eval.run_evals import grade
from ch06_agents.trajectory import grade_trajectory
from ch07_datasets.redact import redact
from common.clock import FakeClock
from common.relay_fake import ask
from ch11_traces import sampling
from ch11_traces.context import (ADDRESS, MUST_KEEP, careful_summarize,
                                 fields_lost, long_session, summarize,
                                 trim_oldest_first)
from ch11_traces.cost import steady_gb, structure_bytes, text_bytes
from ch11_traces.debug import shrink
from ch11_traces.evals import (calls_from_trace, failing_traces, link_judge,
                               trace_to_case)
from ch11_traces.health import (health, orphans, personal_misses,
                                redacting_export)
from ch11_traces.relay_run import (ORDER, WINDOW, Crew, answer_run,
                                   flat_run, loop_run, nightly_batch,
                                   run_batch)
from ch11_traces.render import describe, log_line, render_tree
from ch11_traces.tracer import (SPAN_KINDS, Context, IdGenerator, Tracer,
                                current, extract, inject)


def fresh(seed=11, **kw):
    clock = FakeClock()
    return clock, Tracer(clock, IdGenerator(seed), **kw)


def crew_run(**kw):
    clock, tracer = fresh()
    root = Crew(tracer, clock).run("conv-0412", **kw)
    return tracer, root


def by_kind(spans, kind):
    return [s for s in spans if s.kind == kind]


# --- the tracer ------------------------------------------------------------
def test_nested_spans_share_a_trace_and_point_at_their_parent():
    clock, tracer = fresh()
    with tracer.span("outer", "agent") as outer:
        with tracer.span("inner", "llm") as inner:
            clock.sleep(2)
    assert outer.parent_id is None
    assert inner.parent_id == outer.span_id
    assert inner.trace_id == outer.trace_id
    assert inner.duration == 2 and outer.duration == 2


def test_two_roots_start_two_traces_and_nothing_stays_open():
    clock, tracer = fresh()
    with tracer.span("a", "agent") as a:
        pass
    with tracer.span("b", "agent") as b:
        pass
    assert a.trace_id != b.trace_id
    assert current() is None


def test_same_seed_gives_the_same_ids():
    ids = [IdGenerator(5).trace_id() for _ in range(2)]
    assert ids[0] == ids[1] and len(ids[0]) == 32
    assert len(IdGenerator(5).span_id()) == 16


def test_attributes_events_and_error_status():
    clock, tracer = fresh()
    with pytest.raises(ValueError):
        with tracer.span("boom", "tool", attrs={"a": 1}) as sp:
            sp.set({"b": 2})
            sp.event("note", detail="x")
            raise ValueError("bad")
    assert sp.attributes == {"a": 1, "b": 2}
    assert sp.status == "error"
    assert [e[1] for e in sp.events] == ["note", "exception"]
    assert sp.events[1][2] == {"type": "ValueError", "message": "bad"}
    assert sp in tracer.finished             # a failed span is still kept


def test_traceparent_round_trip():
    clock, tracer = fresh()
    with tracer.span("planner", "agent") as sp:
        header = inject({})
    parts = header["traceparent"].split("-")
    assert [len(p) for p in parts] == [2, 32, 16, 2]
    assert parts[0] == "00" and parts[3] == "01"
    assert extract(header) == Context(sp.trace_id, sp.span_id, True)


@pytest.mark.parametrize("header", [
    "", "garbage",
    "00-" + "0" * 32 + "-00f067aa0ba902b7-01",             # zero trace id
    "00-4bf92f3577b34da6a3ce929d0e0e4736-" + "0" * 16 + "-01",
    "ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    "00-4BF92F3577B34DA6A3CE929D0E0E4736-00f067aa0ba902b7-01",  # upper case
    "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7",     # no flags
])
def test_a_bad_header_starts_a_new_trace_instead_of_crashing(header):
    assert extract({"traceparent": header}) is None


def test_the_w3c_example_parses():
    ctx = extract({"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-"
                                  "00f067aa0ba902b7-01"})
    assert ctx.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert ctx.span_id == "00f067aa0ba902b7" and ctx.sampled


def test_head_sampling_decides_once_and_children_follow():
    clock, tracer = fresh(sampler=lambda trace_id: False)
    with tracer.span("root", "agent"):
        with tracer.span("child", "llm"):
            header = inject({})
    assert tracer.finished == []                   # nothing recorded
    assert header["traceparent"].endswith("-00")   # and the flag says so
    assert extract(header).sampled is False


def test_an_explicit_context_wins_over_the_open_span():
    clock, tracer = fresh()
    with tracer.span("planner", "agent") as planner:
        header = inject({})
    with tracer.span("other", "agent"):
        with tracer.span("worker", "agent", context=extract(header)) as w:
            pass
    assert w.parent_id == planner.span_id
    assert w.trace_id == planner.trace_id


def test_context_is_per_task_under_asyncio():
    clock, tracer = fresh()

    async def worker(name):
        with tracer.span(name, "agent") as sp:
            await asyncio.sleep(0)             # let the other task run
            with tracer.span(name + ".child", "llm") as child:
                pass
        return sp, child

    async def both():
        return await asyncio.gather(worker("a"), worker("b"))

    (a, a_child), (b, b_child) = asyncio.run(both())
    assert a_child.parent_id == a.span_id
    assert b_child.parent_id == b.span_id
    assert a.trace_id != b.trace_id


def test_links_are_recorded_and_are_not_parents():
    clock, tracer = fresh()
    spans = []
    for name in "xyz":
        with tracer.span(name, "agent") as sp:
            spans.append(sp)
    with tracer.span("batch", "agent", links=[s.ctx for s in spans]) as job:
        pass
    assert job.parent_id is None and len(job.links) == 3
    assert job.trace_id not in {s.trace_id for s in spans}


# --- one Relay Crew conversation -----------------------------------------------
def test_the_crew_run_is_one_tree_of_thirteen_spans_of_six_kinds():
    tracer, root = crew_run()
    spans = tracer.finished
    assert len(spans) == 13
    assert {s.kind for s in spans} == set(SPAN_KINDS)
    assert len({s.trace_id for s in spans}) == 1
    assert orphans(spans) == []
    assert [s for s in spans if s.parent_id is None] == [root]


def test_the_printed_tree():
    tracer, _ = crew_run()
    lines = render_tree(tracer.finished)
    assert lines[0] == "trace db5b5fab  conv-0412  13 spans"
    assert lines[1] == "invoke_agent Planner  5.85s"
    assert ("    chat a-large-v2  2.50s  2,800 in / 350 out, $0.0046"
            in lines)
    assert "      ! retry: attempt 1: 429, sleeping 1.00s" in lines
    assert ("    context_trim  0.90s  31,800 -> 7,900 tokens, "
            "lost delivery_address" in lines)
    assert max(len(line) for line in lines) <= 74


def test_the_flat_trace_is_41_siblings_and_collapses_to_one_line():
    clock, tracer = fresh(5)
    flat_run(tracer, clock)
    spans = tracer.finished
    assert len(spans) == 42
    root = next(s for s in spans if s.parent_id is None)
    assert sum(s.parent_id == root.span_id for s in spans) == 41
    assert {s.kind for s in spans} == {"request", "llm"}   # no agent, no plan
    lines = render_tree(spans)
    assert lines[1] == "conversation  425.11s"
    assert lines[2] == "  chat a-large-v2 x41  45.43s"
    assert len(render_tree(spans, collapse=False)) == 43


def turns_of(calls):
    """Group model calls into turns: a gap of over a second is the
    customer typing."""
    turns = [[calls[0]]]
    for before, after in zip(calls, calls[1:]):
        if after.start - before.end > 1:
            turns.append([])
        turns[-1].append(after)
    return turns


def test_every_turn_of_the_flat_conversation_is_fast():
    """INC-4 was quiet: each turn answered well inside the 8 s that
    tail sampling calls slow, so latency could not raise the alarm."""
    clock, tracer = fresh(5)
    flat_run(tracer, clock)
    calls = sorted((s for s in tracer.finished if s.kind == "llm"),
                   key=lambda s: s.start)
    turns = turns_of(calls)
    seconds = [t[-1].end - t[0].start for t in turns]
    assert [len(t) for t in turns] == [4] * 9 + [5]
    assert 3.7 < min(seconds) and max(seconds) < 6.1
    assert max(seconds) < sampling.SLOW_SECONDS


def test_the_researcher_is_a_child_of_the_planner():
    tracer, root = crew_run()
    researcher = next(s for s in tracer.finished
                      if s.name == "invoke_agent Researcher")
    assert researcher.parent_id == root.span_id


def test_a_dropped_header_makes_a_second_trace():
    tracer, root = crew_run(faults={"drop_header"})
    spans = tracer.finished
    assert len({s.trace_id for s in spans}) == 2
    researcher = next(s for s in spans if s.name == "invoke_agent Researcher")
    assert researcher.parent_id is None            # a root of its own
    assert len([s for s in spans if s.trace_id == researcher.trace_id]) == 4
    assert orphans(spans) == []                    # roots, not orphans


def test_retry_events_come_from_chapter_nine():
    tracer, _ = crew_run()
    call = next(s for s in tracer.finished if s.events
                and s.events[0][1] == "retry")
    assert call.events[0][2] == {"detail": "attempt 1: 429, sleeping 1.00s"}
    assert call.duration == pytest.approx(2.5)     # 1.0 s waited + 1.5 s


def test_the_step_guard_totals_land_on_the_root():
    tracer, root = crew_run()
    assert root.attributes["relay.guard.steps"] == 4
    assert root.attributes["relay.guard.tokens"] == 37_680


def test_the_retrieval_span_carries_what_chapter_eight_asked_for():
    tracer, _ = crew_run()
    span = by_kind(tracer.finished, "retrieval")[0]
    a = span.attributes
    assert a["relay.retrieval.status"] == "ok"
    assert a["relay.index.version"] == "v2"
    assert [c["id"] for c in a["relay.retrieval.chunks"]] == [
        "reschedule#0", "reschedule#1", "help-centre#0"]
    assert all({"doc_version", "score"} <= set(c)
               for c in a["relay.retrieval.chunks"])
    assert a["gen_ai.retrieval.top_k"] == 3


def test_every_llm_span_has_the_vital_signs():
    tracer, _ = crew_run()
    for span in by_kind(tracer.finished, "llm"):
        a = span.attributes
        assert {"gen_ai.request.model", "gen_ai.usage.input_tokens",
                "gen_ai.usage.output_tokens", "relay.cost_microusd",
                "gen_ai.response.finish_reasons"} <= set(a)
        assert span.duration > 0 and span.status == "ok"


def test_the_log_line_is_chapter_ones_line_plus_three_ids():
    tracer, _ = crew_run()
    call = by_kind(tracer.finished, "llm")[0]
    line = json.loads(log_line(call))
    assert line["cost_microusd"] == 3_050          # 2,000 x 1 + 210 x 5
    assert line["trace"] == call.trace_id[:8]
    assert line["span"] == call.span_id[:8]
    assert line["parent"] == call.parent_id[:8]
    assert {"model", "input_tokens", "output_tokens", "finish_reason",
            "latency_ms"} <= set(line)             # Chapter 1's fields


# --- context as spans -------------------------------------------------------------
def test_the_scripted_session_is_26_turns_and_31800_tokens():
    turns = long_session()
    assert len(turns) == 26 and sum(t.tokens for t in turns) == 31_800
    assert ADDRESS in turns[1].text


def test_trimming_drops_the_oldest_first_and_loses_the_address():
    turns = long_session()
    kept, dropped = trim_oldest_first(turns, 7_800)
    assert len(dropped) == 21 and dropped[0] == turns[1]
    new = [kept[0], summarize(dropped)] + kept[1:]
    assert sum(t.tokens for t in new) == 7_900
    assert fields_lost(MUST_KEEP, new) == ["delivery_address"]


def test_the_state_span_records_before_after_and_what_was_lost():
    tracer, _ = crew_run()
    a = by_kind(tracer.finished, "state")[0].attributes
    assert (a["relay.context.tokens_before"],
            a["relay.context.tokens_after"]) == (31_800, 7_900)
    assert a["relay.context.turns_dropped"] == 21
    assert a["relay.context.fields_lost"] == ["delivery_address"]
    state = by_kind(tracer.finished, "state")[0]
    assert state.events[0][1:] == ("field_dropped",
                                   {"field": "delivery_address"})


def test_each_model_call_records_what_it_could_see():
    tracer, _ = crew_run()
    seen = {s.name: s.attributes["relay.context.fields_missing"]
            for s in tracer.finished
            if "relay.context.fields_missing" in s.attributes}
    assert seen == {"chat a-small": [], "chat a-large-v2": [
        "delivery_address"]}


def test_a_careful_summarizer_keeps_the_address_and_the_span_says_so():
    tracer, _ = crew_run(summarize_with=careful_summarize)
    a = by_kind(tracer.finished, "state")[0].attributes
    assert a["relay.context.fields_lost"] == []
    assert by_kind(tracer.finished, "state")[0].events == []


# --- errors and Chapter 9's guards --------------------------------------------
def test_the_loop_guard_stops_the_fourth_identical_call():
    clock, tracer = fresh(5)
    agent = loop_run(tracer, clock)
    tools = by_kind(tracer.finished, "tool")
    assert len(tools) == 4 and all(t.status == "error" for t in tools)
    assert tools[0].events[0][2]["message"] == "slot unavailable"
    assert tools[3].events[0][2]["message"] == (
        "loop: reschedule_delivery x4, same args")
    assert agent.events[0][1] == "hand_off_to_human"
    assert len({t.attributes["relay.tool.args_hash"] for t in tools}) == 1


# --- a trace is a transcript you did not plan to grade --------------------------
PATH = {"tools": ["lookup_order", "reschedule_delivery"],
        "args": {"reschedule_delivery": {"order_id": ORDER,
                                         "window": WINDOW}},
        "max_steps": 3}


def test_calls_from_a_trace_have_what_a_trajectory_grader_needs():
    tracer, _ = crew_run()
    calls = calls_from_trace(tracer.finished)
    assert [c["tool"] for c in calls] == ["lookup_order",
                                          "reschedule_delivery"]
    assert calls[1]["args"] == {"order_id": ORDER, "window": WINDOW}
    assert grade_trajectory(PATH, calls) == []


def test_the_grader_flags_the_looping_trace():
    clock, tracer = fresh(5)
    loop_run(tracer, clock)
    problems = grade_trajectory(PATH, calls_from_trace(tracer.finished))
    assert problems == ["missing lookup_order", "calls: 4, limit 3"]


def test_a_judge_span_links_to_the_graded_trace():
    clock, tracer = fresh()
    crew = Crew(tracer, clock)
    good = crew.run("conv-1", summarize_with=careful_summarize)
    bad = crew.run("conv-2")
    link_judge(tracer, good, "pass")
    judge = link_judge(tracer, bad, "fail")
    assert judge.links == [bad.ctx] and judge.parent_id is None
    assert failing_traces(tracer.finished) == [bad.trace_id]


def test_a_failing_trace_becomes_a_case_that_fails_v2_and_passes_v1():
    clock, tracer = fresh()
    root, call = answer_run(tracer, clock,
                            "How long do I have to return a jacket?", "v2")
    case = trace_to_case(root, "returns", r"14 days", r"30 days", "R-32")
    assert case["question"] == "How long do I have to return a jacket?"
    assert case["source"] == "trace" and case["trace_id"] == root.trace_id
    assert grade(case, call.attributes["relay.response.text"])[0] is False
    assert grade(case, ask(case["question"], "v1"))[0] is True
    assert grade(case, ask(case["question"], "v2")) == (
        False, "missing /14 days/")


def test_shrink_finds_a_one_minimal_repro():
    turns = long_session()

    def address_lost(rest):
        said = any(ADDRESS in t.text for t in rest)
        kept, _ = trim_oldest_first([turns[0]] + rest, 7_800)
        return said and "delivery_address" in fields_lost(MUST_KEEP, kept)

    small = shrink(turns[1:], address_lost)
    assert address_lost(small) and len(small) == 5
    for i in range(len(small)):                  # nothing can be removed
        assert not address_lost(small[:i] + small[i + 1:])


def test_shrink_returns_everything_when_nothing_can_go():
    assert shrink([1, 2, 3], lambda xs: sorted(xs) == [1, 2, 3]) == [1, 2, 3]


# --- hygiene --------------------------------------------------------------------
def test_head_sampling_misses_errors_and_tail_sampling_keeps_them():
    traffic = sampling.simulate_traffic()
    head, tail = sampling.compare(traffic)
    assert (sum(t["error"] for t in traffic),
            sum(t["seconds"] > sampling.SLOW_SECONDS for t in traffic)
            ) == (34, 38)
    assert head == (89, 3, 3)
    assert tail == (116, 34, 38)           # every error, every slow trace


def test_head_keep_is_deterministic_and_roughly_the_rate():
    ids = IdGenerator(1)
    kept = sum(sampling.head_keep(ids.trace_id(), 0.10)
               for _ in range(5_000))
    assert 400 < kept < 600
    assert sampling.head_keep("0" * 32, 0.10) is True
    assert sampling.head_keep("f" * 32, 0.10) is False


def test_the_edge_redactor_cleans_free_text_but_cannot_find_names():
    clock, tracer = fresh(export=redacting_export(redact))
    for text in ("for anna.keller@example.com",
                 "for Hannelore Vogt, Lindenstrasse 12"):
        with tracer.span("retrieval", "retrieval",
                         attrs={"gen_ai.retrieval.query.text": text,
                                "relay.tool.args": '{"order_id": "ORD-004829"}'}):
            pass
    first, second = tracer.finished
    assert first.attributes["gen_ai.retrieval.query.text"] == (
        "for <EMAIL_1>")
    assert second.attributes["gen_ai.retrieval.query.text"] == (
        "for Hannelore Vogt, Lindenstrasse 12")        # the honest limit
    assert "ORD-004829" in first.attributes["relay.tool.args"]


def test_tool_arguments_are_redacted_and_identifiers_stay():
    """A ticket's description is free text inside the tool arguments:
    the old hook cleaned only `.text` keys and stored the email."""
    clock, tracer = fresh(export=redacting_export(redact))
    args = {"order_id": ORDER,
            "description": "customer anna.keller@example.com: parcel lost"}
    with tracer.span("execute_tool create_ticket", "tool", attrs={
            "gen_ai.tool.name": "create_ticket",
            "relay.tool.args": json.dumps(args, sort_keys=True)}):
        pass
    stored = json.loads(tracer.finished[0].attributes["relay.tool.args"])
    assert stored == {"order_id": ORDER,
                      "description": "customer <EMAIL_1>: parcel lost"}
    assert personal_misses(tracer.finished, redact) == 0


def test_event_details_are_redacted_too():
    clock, tracer = fresh(export=redacting_export(redact))
    with pytest.raises(ValueError):
        with tracer.span("execute_tool create_ticket", "tool"):
            raise ValueError("bad contact anna.keller@example.com")
    stored = tracer.finished[0]
    assert stored.events[0][2]["message"] == "bad contact <EMAIL_1>"
    assert personal_misses(tracer.finished, redact) == 0


def test_redaction_stores_a_copy_and_leaves_the_live_span_alone():
    """An exporter wrapper works on what it sends, not on the span: the
    only place redaction can work once a span has ended."""
    clock, tracer = fresh(export=redacting_export(redact))
    with tracer.span("retrieval", "retrieval", attrs={
            "gen_ai.retrieval.query.text": "for anna.keller@example.com"}
                     ) as live:
        pass
    stored = tracer.finished[0]
    assert stored is not live and stored.span_id == live.span_id
    assert live.attributes["gen_ai.retrieval.query.text"].endswith(
        "example.com")
    assert stored.attributes["gen_ai.retrieval.query.text"] == (
        "for <EMAIL_1>")


def test_a_skipped_redactor_is_what_personal_misses_counts():
    clock, tracer = fresh()                    # no redaction at all
    with tracer.span("execute_tool create_ticket", "tool", attrs={
            "relay.tool.args": json.dumps(
                {"description": "mail anna.keller@example.com"})}):
        pass
    assert personal_misses(tracer.finished, redact) == 1


def test_an_order_id_in_a_structured_key_is_not_a_personal_miss():
    clock, tracer = fresh()
    Crew(tracer, clock).run("conv-1")
    assert personal_misses(tracer.finished, redact) == 0


def test_health_of_a_fleet_with_known_defects():
    clock, tracer = fresh(export=redacting_export(redact))
    spans = run_batch(tracer, clock, 100)
    h = health(spans, redact)
    assert h["conversations"] == 100 and h["spans"] == 1_295
    assert h["complete"] == pytest.approx(0.92)       # 8 broken of 100
    assert h["orphan_rate"] == pytest.approx(5 / 1_295)
    assert h["attribute_coverage"] == pytest.approx(0.95)
    assert h["personal_misses"] == 4


def test_a_clean_fleet_is_perfectly_healthy():
    clock, tracer = fresh(export=redacting_export(redact))
    crew = Crew(tracer, clock)
    for i in range(5):
        crew.run(f"conv-{i}")
    h = health(tracer.finished, redact)
    assert (h["complete"], h["orphan_rate"], h["attribute_coverage"],
            h["personal_misses"]) == (1.0, 0.0, 1.0, 0)


def test_nightly_batch_has_links_and_no_parent():
    clock, tracer = fresh()
    crew = Crew(tracer, clock)
    roots = [crew.run(f"conv-{i}") for i in (1, 2, 3)]
    job = nightly_batch(tracer, roots)
    assert job.parent_id is None and len(job.links) == 3


# --- cost and retention -------------------------------------------------------------
def test_the_worked_cost_estimate():
    tracer, _ = crew_run()
    structure, text = (structure_bytes(tracer.finished),
                       text_bytes(tracer.finished))
    assert (structure, text) == (5_670, 150_720)
    assert text == (2_210 + 3_150 + 24_300 + 8_020) * 4
    tasks = 900_000
    assert steady_gb(tasks, 1, structure + text, 90) == pytest.approx(
        422.3, abs=0.05)
    assert steady_gb(tasks, 1, structure, 90) == pytest.approx(15.3, abs=0.05)
    # the tiered rule, in the chapter's words: 1.8 GB + 4.6 GB = 6.3 GB
    kept, cause = 0.116, 0.072
    assert steady_gb(tasks, kept, structure, 90) == pytest.approx(
        1.8, abs=0.05)
    assert steady_gb(tasks, cause, text, 14) == pytest.approx(4.6, abs=0.05)
    assert (steady_gb(tasks, kept, structure, 90)
            + steady_gb(tasks, cause, text, 14)) == pytest.approx(6.3,
                                                                  abs=0.05)


def test_describe_prints_every_attribute_and_event():
    tracer, _ = crew_run()
    lines = describe(by_kind(tracer.finished, "state")[0])
    assert lines[0] == "context_trim  (state, ok)"
    assert "  relay.context.tokens_before: 31800" in lines
    assert lines[-1].startswith("  event field_dropped")


def test_identical_failures_collapse_but_the_guard_stop_does_not():
    clock, tracer = fresh(5)
    loop_run(tracer, clock)
    lines = render_tree(tracer.finished)
    assert ("  execute_tool reschedule_delivery x3  0.60s  "
            "ERROR ToolError: slot unavailable") in lines
    assert len(render_tree(tracer.finished, collapse=False)) == 11
    assert any("RuntimeError: loop: reschedule_delivery x4" in l
               for l in lines)


def test_the_demo_runs_and_prints_the_headline_numbers(capsys):
    from ch11_traces import demo
    demo.main()
    out = capsys.readouterr().out
    for line in ("tree completeness   92%", "orphan span rate    0.4%",
                 "attribute coverage  95%",
                 "personal data found in stored spans: 4",
                 "26 turns shrink to 5, plus the system prompt:",
                 "keep everything, text, 90 days:   422.3 GB",
                 'stored: {"description": "lost; <EMAIL_1>", '
                 '"order_id": "ORD-004829"}'):
        assert line in out


def test_try_it_yourself_answers():
    traffic = sampling.simulate_traffic()
    assert sampling.compare(traffic, head_rate=0.30)[0] == (287, 7, 8)
    assert sampling.compare(traffic, head_rate=0.50)[0] == (515, 12, 21)
    clock, tracer = fresh()
    Crew(tracer, clock).run("conv-0412")
    structure, text = (structure_bytes(tracer.finished),
                       text_bytes(tracer.finished))
    kept = sampling.compare(traffic)[1][0] / len(traffic)
    cause = sum(t["error"] or t["seconds"] > sampling.SLOW_SECONDS
                for t in traffic) / len(traffic)
    assert (kept, cause) == (0.116, 0.072)
    assert steady_gb(900_000, kept, structure, 30) == pytest.approx(
        0.59, abs=0.005)
    assert steady_gb(900_000, cause, text, 7) == pytest.approx(
        2.28, abs=0.005)

    class NoHeaders(Crew):              # every worker gets an empty header
        def hop(self, name, msg, body):
            super().hop(name, {**msg, "headers": {}}, body)

    clock, tracer = fresh()
    crew = NoHeaders(tracer, clock)
    crew.run("conv-0412")
    sizes = sorted(len([s for s in tracer.finished if s.trace_id == t])
                   for t in {s.trace_id for s in tracer.finished})
    assert sizes == [3, 3, 3, 4]
    h = health(tracer.finished, redact)
    assert h["complete"] == 0.0 and h["orphan_rate"] == 0.0


def test_a_worker_context_starts_with_no_open_span():
    clock, tracer = fresh()
    with tracer.span("planner", "agent"):
        seen = contextvars.Context().run(current)
    assert seen is None
