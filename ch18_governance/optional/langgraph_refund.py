"""Pause before issue_refund, wait for a person, then resume.

Run once in a throwaway virtualenv: langgraph 1.2.12 with
langgraph-checkpoint 4.2.0, Python 3.12, 5 October 2026. It is not run by
pytest or CI.  Setup:  python3 -m venv /tmp/lg && /tmp/lg/bin/pip install
langgraph  then  /tmp/lg/bin/python langgraph_refund.py
"""
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.types import Command, interrupt

entered = []                     # counts how often the review node starts


class Case(TypedDict):
    call: dict                   # the proposed issue_refund call
    decision: str
    done: str


def review(state: Case):
    entered.append("review")     # runs again on resume: keep it harmless
    packet = {"proposed": state["call"], "why": "above the $50 line"}
    answer = interrupt(packet)   # pauses here; the state is saved
    return {"decision": answer["decision"],
            "call": answer.get("call", state["call"])}


def act(state: Case):
    if state["decision"] == "reject":
        return {"done": "nothing sent"}
    return {"done": f"issue_refund {state['call']['amount_cents']}"}


graph = StateGraph(Case).add_sequence([review, act])
graph.add_edge(START, "review")
app = graph.compile(checkpointer=InMemorySaver())   # a database in prod
config = {"configurable": {"thread_id": "case-8812"}}

call = {"order_id": "ORD-004830", "amount_cents": 40_000}
paused = app.invoke({"call": call}, config)
print("paused:", paused["__interrupt__"][0].value["why"])
print("sent so far:", paused.get("done"), "| next node:",
      app.get_state(config).next)

edited = dict(call, amount_cents=2_500)
done = app.invoke(Command(resume={"decision": "edit", "call": edited}),
                  config)
print("after resume:", done["done"])
print("review node started", len(entered), "times")
