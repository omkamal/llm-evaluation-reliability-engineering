"""One Relay Crew conversation, traced. Offline: every number is scripted.

It reuses Chapter 1 (the cost of a call), Chapter 8 (the retrieval tool)
and Chapter 9 (retries, the step guard, the loop guard)."""
import contextvars
import hashlib
import json
import random
from datetime import date

from ch01_anatomy.call import Completion, cost_microusd
from ch08_rag.corpus import snapshot
from ch08_rag.lifecycle import build_index
from ch08_rag.tool import lookup_policy
from ch09_when_calls_fail.budget import RetryBudget
from ch09_when_calls_fail.guard import StepGuard
from ch09_when_calls_fail.loop_guard import LoopGuard
from ch09_when_calls_fail.retry import call_with_retry
from ch11_traces.context import (MUST_KEEP, fields_lost, long_session,
                                 summarize, traced_trim)
from ch11_traces.tracer import extract, inject
from common.relay_fake import ask


class NoJitter:
    """Scripted run: wait exactly what Retry-After asks (Ch 9 adds jitter)."""
    @staticmethod
    def uniform(lo, hi):
        return 0.0



class NoJitter:
    """Scripted run: wait exactly what Retry-After asks (Ch 9 adds jitter)."""
    @staticmethod
    def uniform(lo, hi):
        return 0.0


TODAY = date(2026, 10, 4)
ORDER, WINDOW = "ORD-004829", "Thu 08:00-10:00"
QUERY = "rescheduling a delivery"


class ToolError(Exception):
    pass


def args_hash(args):
    text = json.dumps(args, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:6]


class Crew:
    """Planner, Researcher, Summarizer and Actioner, each in its own
    worker. `faults` switches on the defects the health check hunts."""

    def __init__(self, tracer, clock, seed=7):
        self.tracer, self.clock = tracer, clock
        self.rng = random.Random(seed)
        self.index = build_index("v2", snapshot(TODAY), TODAY)

    def llm(self, model, usage, seen=None, flaky=False):
        """One model call: guarded, retried, timed and costed."""
        tokens_in, tokens_out, ms = usage
        done = Completion("", "stop", tokens_in, tokens_out, ms)
        self.guard.before_step(tokens_in + tokens_out,
                               cost_microusd(done) / 1_000_000)
        with self.tracer.span(f"chat {model}", "llm") as sp:
            if flaky:                       # Provider A answers 429 once
                replies = iter([(429, 1.0), (200, None)])
                call_with_retry(lambda: next(replies), self.budget,
                                self.clock.now() + 20, clock=self.clock,
                                rng=NoJitter(), log=lambda m: sp.event(
                                    "retry", detail=m.strip()))
            self.clock.sleep(ms / 1000)
            sp.set({"gen_ai.operation.name": "chat",
                    "gen_ai.provider.name": "provider_a",
                    "gen_ai.request.model": model,
                    "gen_ai.response.finish_reasons": ["stop"]})
            if "no_usage" not in self.faults:
                sp.set({"gen_ai.usage.input_tokens": tokens_in,
                        "gen_ai.usage.output_tokens": tokens_out,
                        "relay.cost_microusd": cost_microusd(done)})
            if seen is not None:            # what the model could see
                sp.set({"relay.context.fields_missing":
                        fields_lost(MUST_KEEP, seen)})

    def tool(self, name, tier, args, seconds):
        with self.tracer.span(f"execute_tool {name}", "tool") as sp:
            self.clock.sleep(seconds)
            sp.set({"gen_ai.operation.name": "execute_tool",
                    "gen_ai.tool.name": name, "relay.tool.tier": tier,
                    "relay.tool.args": json.dumps(args, sort_keys=True),
                    "relay.tool.args_hash": args_hash(args),
                    "relay.tool.verified": True})

    def retrieve(self, query):
        with self.tracer.span("retrieval policy_index", "retrieval") as sp:
            self.clock.sleep(0.08)
            found = lookup_policy(self.index, query)
            sp.set({"gen_ai.operation.name": "retrieval",
                    "gen_ai.data_source.id": "policy_index",
                    "gen_ai.retrieval.top_k": 3,
                    "gen_ai.retrieval.query.text": query,
                    "relay.retrieval.status": found["status"],
                    "relay.index.version": found["index_version"],
                    "relay.retrieval.chunks": [
                        {"id": c["id"], "doc_version": c["doc_version"],
                         "score": c["score"]} for c in found["chunks"]]})

    def hop(self, name, msg, body):
        """Run one agent like a separate process: it knows only its
        message, and a dropped header starts a new trace."""
        def worker():
            header = {} if (name == "Researcher" and "drop_header"
                            in self.faults) else msg["headers"]
            with self.tracer.span(
                    f"invoke_agent {name}", "agent", context=extract(header),
                    attrs={"gen_ai.operation.name": "invoke_agent",
                           "gen_ai.agent.name": name,
                           "gen_ai.conversation.id": msg["session"]}):
                body()
        contextvars.Context().run(worker)

    def researcher(self):
        query = QUERY + (" for anna.keller@example.com"
                         if "leak_email" in self.faults else "")
        self.retrieve(query)
        self.llm("a-large-v2", (2_800, 350, 1_500), flaky=True)
        self.tool("lookup_order", 0, {"order_id": ORDER}, 0.15)

    def summarizer(self):
        turns = long_session()
        def summary(dropped):               # the model call inside the trim
            self.llm("a-small", (sum(t.tokens for t in dropped), 200, 900),
                     seen=turns)
            return self.summarize(dropped)
        self.context = traced_trim(self.tracer, turns, 8_000, summary)

    def actioner(self):
        self.llm("a-large-v2", (sum(t.tokens for t in self.context), 120,
                                800), seen=self.context)
        self.tool("reschedule_delivery", 1,
                  {"order_id": ORDER, "window": WINDOW}, 0.22)

    def run(self, session, faults=(), summarize_with=summarize):
        self.faults, self.summarize = set(faults), summarize_with
        self.guard = StepGuard(clock=self.clock)
        self.budget = RetryBudget()         # Chapter 9: shared, per run
        with self.tracer.span("invoke_agent Planner", "agent", attrs={
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": "Planner",
                "gen_ai.conversation.id": session}) as root:
            with self.tracer.span("plan Planner", "plan", attrs={
                    "gen_ai.operation.name": "plan"}):
                self.llm("a-large-v2", (2_000, 210, 1_200))
            for name, body in (("Researcher", self.researcher),
                               ("Summarizer", self.summarizer),
                               ("Actioner", self.actioner)):
                msg = {"headers": inject({}), "session": session}
                self.hop(name, msg, body)       # the baton passes
            root.set({"relay.guard.steps": self.guard.used["steps"],
                      "relay.guard.tokens": self.guard.used["tokens"]})
        return root


def flat_run(tracer, clock, session="conv-0388", calls=41, seed=41):
    """The old instrumentation: one span for a whole conversation and a
    sibling for every model call in it. Ten turns of about four calls,
    each turn answered in a few seconds; the customer types in between."""
    rng = random.Random(seed)
    with tracer.span("conversation", "request",
                     attrs={"gen_ai.conversation.id": session}) as root:
        for i in range(calls):
            if i and i % 4 == 0 and i < calls - 1:
                clock.sleep(rng.uniform(20, 60))   # the customer's turn
            tokens_in, tokens_out = rng.randint(1_500, 6_000), 150
            with tracer.span("chat a-large-v2", "llm") as sp:
                clock.sleep(rng.uniform(0.8, 1.4))
                sp.set({"gen_ai.usage.input_tokens": tokens_in,
                        "gen_ai.usage.output_tokens": tokens_out})
    return root


def loop_run(tracer, clock, session="conv-0391"):
    """Chapter 9's loop guard, seen from the trace."""
    guard = LoopGuard()
    args = {"order_id": ORDER, "window": WINDOW}
    with tracer.span("invoke_agent Actioner", "agent", attrs={
            "gen_ai.conversation.id": session}) as agent:
        while True:
            try:
                with tracer.span("execute_tool reschedule_delivery",
                                 "tool", attrs={
                        "gen_ai.tool.name": "reschedule_delivery",
                        "relay.tool.tier": 1, "relay.tool.verified": True,
                        "relay.tool.args": json.dumps(args, sort_keys=True),
                        "relay.tool.args_hash": args_hash(args)}):
                    guard.check("reschedule_delivery", args)
                    clock.sleep(0.2)
                    raise ToolError("slot unavailable")
            except ToolError:
                continue                    # the agent tries again
            except RuntimeError as why:     # the guard stopped the loop
                clock.sleep(0.05)           # a moment to give up
                agent.event("hand_off_to_human", reason=str(why))
                return agent


def run_batch(tracer, clock, n=100):
    """n conversations; every few carry a defect, as real fleets do."""
    crew, export = Crew(tracer, clock), tracer.export
    for i in range(n):
        faults = set()
        if i % 25 == 4:
            faults.add("drop_header")       # a queue that eats headers
        if i % 20 == 13:
            faults.add("no_usage")          # a client without usage data
        if i % 25 == 17:
            faults.add("leak_email")        # a service that skips redaction
        tracer.export = (lambda s: s) if "leak_email" in faults else export
        crew.run(f"conv-{i:04d}", faults)
        if i % 20 == 9:                     # a worker died before flushing
            tracer.finished[:] = [s for s in tracer.finished
                                  if not (s.name == "invoke_agent Summarizer"
                                          and s.attributes[
                                              "gen_ai.conversation.id"]
                                          == f"conv-{i:04d}")]
        clock.sleep(30)
    tracer.export = export
    return tracer.finished


def answer_run(tracer, clock, question, version, session="conv-0377"):
    """A short run that keeps the words (kept only for sampled traces):
    the customer's request on the root, the reply on the model call."""
    with tracer.span("invoke_agent Planner", "agent", attrs={
            "gen_ai.conversation.id": session,
            "relay.request.text": question}) as root:
        with tracer.span("chat a-large-v2", "llm") as call:
            clock.sleep(1.1)
            call.set({"relay.response.text": ask(question, version)})
    return root, call


def nightly_batch(tracer, roots):
    """One job over many finished sessions: it cannot have many parents,
    so it LINKS to each session's root."""
    with tracer.span("invoke_agent Summarizer (nightly)", "agent",
                     links=[r.ctx for r in roots]) as job:
        pass
    return job
