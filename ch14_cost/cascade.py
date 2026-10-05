"""A cascade and a router over two tiers, on invented tasks.

A case is one task with its outcomes already decided by a seeded luck
draw, so every policy can be run on the SAME cases (a paired test).
"""
import random
from dataclasses import dataclass

from ch12_slos.tasks import Task, percentile
from ch14_cost.economics import PREFIX, REPLY
from ch14_cost.prices import call_usd

SECONDS = {"small": 0.8, "frontier": 2.4, "check": 0.1, "classify": 0.3}
CLASSIFIER_TOKENS = 300       # a router's classifier is a tiny call


@dataclass(frozen=True)
class Case:
    hard: bool          # the small tier rarely solves it
    small_ok: bool      # the small tier's answer is right
    big_ok: bool        # the frontier tier's answer is right
    check_draw: float   # luck the quick check uses
    router_draw: float  # luck the router's classifier uses


def make_cases(n=1000, seed=14, hard_share=0.18):
    rng = random.Random(seed)
    cases = []
    for _ in range(n):
        hard, luck = rng.random() < hard_share, rng.random()
        # easy: both tiers fail alike, 3% of the time; hard: small 10%
        # right, frontier 88% right
        small_ok = luck < (0.10 if hard else 0.97)
        big_ok = luck < (0.88 if hard else 0.97)
        cases.append(Case(hard, small_ok, big_ok, rng.random(),
                          rng.random()))
    return cases


def check_passes(case, true_negative, false_alarm=0.03):
    """The quick check at the gate: a small judge (Chapter 5).

    It fails a wrong answer with probability `true_negative`, and a
    right one with probability `false_alarm`.
    """
    if case.small_ok:
        return case.check_draw >= false_alarm
    return case.check_draw >= true_negative


def frontier_only(cases):
    usd = call_usd("frontier", PREFIX, REPLY)
    return [Task(SECONDS["frontier"], usd, c.big_ok) for c in cases], 0


def cascade(cases, true_negative=0.95, cap_usd=None):
    """Small tier first; step up to frontier when the check fails."""
    small = call_usd("small", PREFIX, REPLY)
    big = call_usd("frontier", PREFIX, REPLY)
    first_secs = SECONDS["small"] + SECONDS["check"]
    tasks, stepped, held, big_spend = [], 0, 0, 0.0
    for c in cases:
        task = Task(first_secs, small, c.small_ok)
        if not check_passes(c, true_negative):
            if cap_usd is not None and big_spend + big > cap_usd:
                held += 1        # cap reached: flag it, no step up
            else:
                stepped += 1
                big_spend += big
                task = Task(first_secs + SECONDS["frontier"],
                            small + big, c.big_ok)
        tasks.append(task)
    return tasks, stepped, held


def router(cases, hit_rate=0.90, false_hard=0.05):
    """A classifier picks the tier up front; nothing checks the answer."""
    cheap = call_usd("small", CLASSIFIER_TOKENS, 10)
    tasks, to_big = [], 0
    for c in cases:
        says_hard = (c.router_draw < hit_rate if c.hard
                     else c.router_draw < false_hard)
        tier = "frontier" if says_hard else "small"
        to_big += says_hard
        usd = cheap + call_usd(tier, PREFIX, REPLY)
        secs = SECONDS["classify"] + SECONDS[tier]
        ok = c.big_ok if says_hard else c.small_ok
        tasks.append(Task(secs, usd, ok))
    return tasks, to_big


def summary(tasks):
    """(dollars per task, resolved share, per resolved task, p95 s)."""
    spend = sum(t.usd for t in tasks)
    done = sum(t.resolved for t in tasks)
    return (spend / len(tasks), done / len(tasks), spend / done,
            percentile([t.seconds for t in tasks], 95))


def small_only(cases):
    usd = call_usd("small", PREFIX, REPLY)
    return [Task(SECONDS["small"], usd, c.small_ok) for c in cases]
