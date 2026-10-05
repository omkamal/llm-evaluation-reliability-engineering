"""Every Chapter 11 output.   python3 -m ch11_traces.demo"""
from ch03_first_eval.run_evals import grade
from ch06_agents.trajectory import grade_trajectory
from ch07_datasets.redact import redact
from common.clock import FakeClock
from common.relay_fake import ask
from ch11_traces import sampling
from ch11_traces.context import (ADDRESS, MUST_KEEP, careful_summarize,
                                 fields_lost, long_session,
                                 trim_oldest_first)
from ch11_traces.cost import structure_bytes, steady_gb, text_bytes
from ch11_traces.debug import shrink
from ch11_traces.evals import (calls_from_trace, failing_traces, link_judge,
                               trace_to_case)
from ch11_traces.health import edge_hook, health
from ch11_traces.relay_run import (ORDER, WINDOW, Crew, answer_run,
                                   flat_run, loop_run, nightly_batch,
                                   run_batch)
from ch11_traces.render import describe, log_line, render_tree
from ch11_traces.tracer import IdGenerator, Tracer, extract, inject


def fresh(seed=11, **kw):
    clock = FakeClock()
    return clock, Tracer(clock, IdGenerator(seed), **kw)


def ladder():
    print("== rung two: the log line grows three ids")
    clock, tracer = fresh()
    Crew(tracer, clock).run("conv-0412")
    first_call = next(s for s in tracer.finished if s.kind == "llm")
    print(log_line(first_call))


def old_and_new():
    print("== the run the old instrumentation saw")
    clock, tracer = fresh(5)
    flat_run(tracer, clock)
    print("\n".join(render_tree(tracer.finished)))
    print("== the same kind of run, as a tree")
    clock, tracer = fresh()
    Crew(tracer, clock).run("conv-0412")
    print("\n".join(render_tree(tracer.finished)))
    print("== one retrieval span, in full")
    span = next(s for s in tracer.finished if s.kind == "retrieval")
    print("\n".join(describe(span)))


def errors():
    print("== an error is data")
    clock, tracer = fresh(5)
    loop_run(tracer, clock)
    print("\n".join(render_tree(tracer.finished)))
    print("== a trajectory grader reads the trace")
    path = {"tools": ["lookup_order", "reschedule_delivery"],
            "args": {"reschedule_delivery": {"order_id": ORDER,
                                             "window": WINDOW}},
            "max_steps": 3}
    print("loop run:", grade_trajectory(path, calls_from_trace(
        tracer.finished)))
    clock, tracer = fresh()
    Crew(tracer, clock).run("conv-0412")
    print("crew run:", grade_trajectory(path, calls_from_trace(
        tracer.finished)))


def handoffs():
    print("== the baton")
    clock, tracer = fresh()
    with tracer.span("invoke_agent Planner", "agent"):
        header = inject({})["traceparent"]
    print("traceparent:", header)
    version, trace_id, parent_id, flags = header.split("-")
    print(f"sampled bit set: {bool(int(flags, 16) & 1)}; "
          f"parsed back: {extract({'traceparent': header}) is not None}")
    print("a header cut short:", extract({"traceparent": header[:-3]}))
    print("== a handoff that drops the header")
    clock, tracer = fresh()
    Crew(tracer, clock).run("conv-0412", faults={"drop_header"})
    print("\n".join(l for l in render_tree(tracer.finished)
                    if not l.startswith("  ")))
    print("== parent versus link")
    clock, tracer = fresh()
    crew = Crew(tracer, clock)
    roots = [crew.run(f"conv-{i}") for i in (1, 2, 3)]
    job = nightly_batch(tracer, roots)
    print(f"nightly job: parent {job.parent_id}, {len(job.links)} links")


def trim():
    print("== what the model saw")
    clock, tracer = fresh()
    Crew(tracer, clock).run("conv-0412")
    state = next(s for s in tracer.finished if s.kind == "state")
    print("\n".join(describe(state)))
    for s in tracer.finished:
        if "relay.context.fields_missing" in s.attributes:
            missing = s.attributes["relay.context.fields_missing"]
            print(f"{s.name:<16}",
                  "missing " + ", ".join(missing) if missing
                  else "saw every must-keep field")
    print("== the same run with a careful summarizer")
    clock, tracer = fresh()
    Crew(tracer, clock).run("conv-0412", summarize_with=careful_summarize)
    print("\n".join(l for l in render_tree(tracer.finished)
                    if "context_trim" in l))


def hygiene():
    print("== head or tail sampling")
    traces = sampling.simulate_traffic()
    errors_n = sum(t["error"] for t in traces)
    slow_n = sum(t["seconds"] > sampling.SLOW_SECONDS for t in traces)
    print(f"{len(traces):,} traces: {errors_n} errors, {slow_n} slow")
    for name, (kept, bad, slow) in zip(("head 10%", "tail"),
                                       sampling.compare(traces)):
        print(f"{name:<9} kept {kept} traces, {bad} of {errors_n} errors, "
              f"{slow} of {slow_n} slow")
    print("== redaction at the edge")
    clock, tracer = fresh(on_end=edge_hook(redact))
    for text in ("rescheduling for anna.keller@example.com",
                 "rescheduling for Hannelore Vogt, Lindenstrasse 12"):
        with tracer.span("retrieval policy_index", "retrieval", attrs={
                "gen_ai.retrieval.query.text": text}):
            pass
        print("stored:", tracer.finished[-1].attributes[
            "gen_ai.retrieval.query.text"])
    print("== a score attached to the trace it grades")
    clock, tracer = fresh()
    crew = Crew(tracer, clock)
    careful = crew.run("conv-0410", summarize_with=careful_summarize)
    lossy = crew.run("conv-0412")
    for root in (careful, lossy):
        saw = [s for s in tracer.finished if s.trace_id == root.trace_id
               and s.attributes.get("relay.context.fields_missing")]
        link_judge(tracer, root, "fail" if saw else "pass")
    bad = failing_traces(tracer.finished)
    print(f"judged 2 conversations, {len(bad)} fail")
    for trace_id in bad:
        session = next(s.attributes["gen_ai.conversation.id"]
                       for s in tracer.finished if s.trace_id == trace_id
                       and "gen_ai.conversation.id" in s.attributes)
        print(f"judge_v2 fail -> trace {trace_id[:8]} ({session})")


def fleet():
    print("== trace health, 100 simulated conversations")
    clock, tracer = fresh(on_end=edge_hook(redact))
    spans = run_batch(tracer, clock, 100)
    h = health(spans, redact)
    print(f"{h['conversations']} conversations, {h['spans']:,} spans")
    print(f"tree completeness   {h['complete']:.0%}")
    print(f"orphan span rate    {h['orphan_rate']:.1%}")
    print(f"attribute coverage  {h['attribute_coverage']:.0%}")
    print(f"personal data found in stored spans: {h['personal_misses']}")


def cost():
    print("== what a trace costs to keep (illustrative)")
    clock, tracer = fresh()
    Crew(tracer, clock).run("conv-0412")
    spans = tracer.finished
    structure, text = structure_bytes(spans), text_bytes(spans)
    print(f"{len(spans)} spans, {structure:,} bytes as JSON; "
          f"message text would add {text:,}")
    tasks = 900_000                      # Chapter 12's task layer, 30 days
    traffic = sampling.simulate_traffic()
    cause = sum(t["error"] or t["seconds"] > sampling.SLOW_SECONDS
                for t in traffic) / len(traffic)
    kept = sampling.compare(traffic)[1][0] / len(traffic)
    everything = steady_gb(tasks, 1, structure + text, 90)
    structure_only = steady_gb(tasks, 1, structure, 90)
    tiered = (steady_gb(tasks, kept, structure, 90)
              + steady_gb(tasks, cause, text, 14))
    print(f"keep everything, text, 90 days:  {everything:6.1f} GB")
    print(f"keep everything, no text, 90 d:  {structure_only:6.1f} GB")
    print(f"tiered ({kept:.1%} structure 90 d, {cause:.1%} text 14 d): "
          f"{tiered:.1f} GB")


def debugging():
    print("== a trace becomes a case")
    clock, tracer = fresh()
    root, call = answer_run(tracer, clock,
                            "How long do I have to return a jacket?", "v2")
    case = trace_to_case(root, "returns", r"14 days", r"30 days", "R-31")
    print(case["id"], case["source"], repr(case["question"]))
    for version in ("v1", "v2"):
        ok, why = grade(case, ask(case["question"], version))
        print(f"  Relay {version}: {'pass' if ok else 'FAIL'} ({why})")
    print("== shrinking the repro")
    turns = long_session()

    def address_lost(rest):
        """Fails when the address was said and the trim lost it."""
        said = any(ADDRESS in t.text for t in rest)
        kept, _ = trim_oldest_first([turns[0]] + rest, 7_800)
        return said and "delivery_address" in fields_lost(MUST_KEEP, kept)
    small = shrink(turns[1:], address_lost)
    print(f"{len(turns)} turns shrink to {len(small)}, plus the system "
          "prompt:")
    for t in small:
        print(f"  {t.role:<8} {t.tokens:>6}  {t.text}")


def main():
    for part in (ladder, old_and_new, errors, handoffs, trim, hygiene,
                 fleet, cost, debugging):
        part()


if __name__ == "__main__":
    main()
