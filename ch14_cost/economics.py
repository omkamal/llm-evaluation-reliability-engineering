"""Token economics: a conversation re-sends its history every turn."""
from ch12_slos.tasks import Task, cost_per_resolved
from ch14_cost.prices import call_usd

PREFIX = 3000        # tokens sent on every turn: system, tools, policy
NEW_PER_TURN = 600   # tokens each turn adds to the history
REPLY = 250          # tokens of answer per call
CALLS_PER_TASK = 6   # model calls in one typical task

# (share of conversations, shortest, longest) in turns; invented mix
LENGTH_MIX = [(0.40, 1, 2), (0.30, 3, 4), (0.14, 5, 8),
              (0.08, 9, 12), (0.08, 13, 25)]


def turn_input(turn):
    """Input tokens sent on turn 1, 2, 3 ...: the history so far."""
    return PREFIX + NEW_PER_TURN * (turn - 1)


def cumulative_input(turns):
    """All input tokens sent over a conversation of this many turns."""
    return sum(turn_input(t) for t in range(1, turns + 1))


def conversation_usd(turns, tier="frontier"):
    return sum(call_usd(tier, turn_input(t), REPLY)
               for t in range(1, turns + 1))


def long_session_shares(mix=LENGTH_MIX, over=12):
    """(share of conversations, share of input tokens) beyond `over`."""
    total = long_tokens = long_share = 0.0
    for share, lo, hi in mix:
        turns = range(lo, hi + 1)
        mean_tokens = sum(cumulative_input(t) for t in turns) / len(turns)
        total += share * mean_tokens
        if lo > over:
            long_tokens += share * mean_tokens
            long_share += share
    return long_share, long_tokens / total


def task_usd(tier="frontier", calls=CALLS_PER_TASK):
    return calls * call_usd(tier, PREFIX, REPLY)


def resolved_cost(usd, resolved_share, n=100):
    """Cost per resolved task: Chapter 12's function, n tasks."""
    done = round(n * resolved_share)
    tasks = [Task(5.3, usd, i < done) for i in range(n)]
    return cost_per_resolved(tasks)


def eaters():
    """Hidden token eaters, as extra dollars on one six-call task."""
    base = task_usd()
    extra = {
        "whole shipment history, +2,500 tokens a call":
            CALLS_PER_TASK * call_usd("frontier", 2500, 0),
        "hidden reasoning, 1,500 tokens on 2 calls":
            2 * call_usd("frontier", 0, 0, hidden=1500),
        "one retry: the same call paid twice":
            call_usd("frontier", PREFIX, REPLY),
        "bloated system prompt, +1,200 tokens a call":
            CALLS_PER_TASK * call_usd("frontier", 1200, 0),
    }
    return base, extra
