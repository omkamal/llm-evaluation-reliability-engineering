"""Chapter 1 as tests. `pytest -q ch01_anatomy`"""
import json
import random

from ch01_anatomy.agent_loop import MAX_STEPS, run_agent
from ch01_anatomy.call import complete, cost_microusd, count_tokens, log_line
from ch01_anatomy.context import fit_to_window
from ch01_anatomy.sampling import sample

PROMPT = "Where is order ORD-004829? Reply in one sentence."
ANSWER = "It left the depot this morning and arrives tomorrow."


def test_a_call_is_metered():
    c = complete(PROMPT, answer=ANSWER, max_tokens=40)
    assert (c.input_tokens, c.output_tokens, c.finish_reason) == (12, 10, "stop")
    assert cost_microusd(c) == 12 * 1 + 10 * 5            # output costs five times input
    line = json.loads(log_line("req-001", "a-large-v1", c))
    assert line["cost_microusd"] == 62 and line["request_id"] == "req-001"


def test_a_short_limit_cuts_the_answer_off_and_says_so():
    c = complete(PROMPT, answer=ANSWER, max_tokens=5)
    assert c.finish_reason == "length" and c.text == "It left the depot this"


def test_token_count_counts_words_and_punctuation():
    assert count_tokens("Hi, there!") == 4


def test_temperature_zero_is_the_same_every_time_and_temperature_one_is_not():
    options, logits = ["refund", "return", "replace"], [2.0, 1.6, 0.4]
    rng = random.Random(2)
    assert len({sample(options, logits, 0, rng) for _ in range(20)}) == 1
    assert len({sample(options, logits, 1.0, rng) for _ in range(20)}) > 1


def test_the_window_drops_the_oldest_turns_and_says_what_it_dropped():
    turns = ["You are Relay.", "My address is 14 Elm Street, Apt 3.",
             "I ordered a lamp last week.", "It has not arrived.", "When will it be here?"]
    kept, dropped = fit_to_window(turns, window_tokens=20)
    assert kept[0] == "You are Relay." and kept[-1] == "When will it be here?"
    assert "My address is 14 Elm Street, Apt 3." in dropped


def test_nothing_is_dropped_when_everything_fits():
    kept, dropped = fit_to_window(["sys", "a", "b"], window_tokens=100)
    assert dropped == [] and len(kept) == 3


def test_the_agent_loop_runs_a_tool_then_answers():
    script = iter([("tool", "lookup_order", {"order_id": "ORD-004829"}), ("answer", "Tomorrow.")])
    answer, history = run_agent("Where is my order?", lambda h: next(script),
                                {"lookup_order": lambda order_id: "out for delivery"})
    assert answer == "Tomorrow." and [k for k, _ in history] == ["user", "tool_call", "tool_result"]


def test_the_agent_loop_stops_at_the_step_cap():
    calls = []
    forever = lambda h: (calls.append(1), ("tool", "lookup_order", {"order_id": "x"}))[1]
    answer, _ = run_agent("hi", forever, {"lookup_order": lambda order_id: "?"})
    assert len(calls) == MAX_STEPS and "person" in answer
