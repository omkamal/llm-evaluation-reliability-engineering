"""A canary release with automatic rollback, on an injected clock.

A small share of live chats goes to the candidate, the rest to the
control, at the same time. Guard metrics compare the two; the first
guard that is clearly worse, or an error budget burning too fast,
sends all traffic back. The clock is injected, so hours cost nothing.
"""
import random
from dataclasses import dataclass, field

from ch04_numbers.stats import difference_ci
from ch12_slos.burn import SLO, Rule, Series, window_burn
from ch16_release.traffic import counts, make_chat


@dataclass(frozen=True)
class Guard:
    name: str
    flag: str        # the Outcome field that is True when a chat is bad
    margin: float    # how much worse than control we accept, in rate


GUARDS = (
    Guard("invalid output", "invalid", 0.01),
    Guard("slow first token", "slow", 0.03),
    Guard("reschedule share", "acted", 0.05),
    Guard("unasked action", "false_act", 0.02),   # audited chats only
    Guard("wrong policy", "wrong_policy", 0.03),  # audited chats only
)
# Chapter 12's rule, shortened to fit a canary: 14.4x over 30 min and 5 min
BURN = Rule("rollback", 14.4, 1800, 300)


def verdict(guard, canary, control, min_n=30):
    """'worse', 'ok' or 'wait' for one guard: canary against control."""
    bad_c, n_c = counts(canary, guard.flag)
    bad_k, n_k = counts(control, guard.flag)
    if n_c < min_n:
        return "wait"                          # too little to judge
    _, (lo, hi) = difference_ci(bad_k, n_k, bad_c, n_c)
    if lo > guard.margin:
        return "worse"       # even the kind end of the interval is bad
    if hi <= guard.margin:
        return "ok"          # even the harsh end is acceptable
    return "wait"


def burning(series, min_chats=100):
    """Both windows above the rule's burn rate, on enough chats."""
    if series.window(BURN.long_s)[1] < min_chats:
        return None
    long_b = window_burn(series, BURN.long_s, SLO)
    short_b = window_burn(series, BURN.short_s, SLO)
    if long_b > BURN.burn and short_b > BURN.burn:
        return f"burn {long_b:.1f}x (30 min), {short_b:.1f}x (5 min)"
    return None


@dataclass
class CanaryResult:
    decision: str                 # "promoted", "rolled back" or "held"
    share: float                  # the share when it ended
    minutes: int
    reason: str
    exposed: int                  # chats the candidate served
    unasked: int                  # reschedules nobody asked for
    failed: int = 0               # errors the candidate's chats saw
    log: list = field(default_factory=list)


class Canary:
    def __init__(self, control, candidate, clock, per_minute=100,
                 steps=(0.05, 0.25, 0.5), min_minutes=30, seed=7,
                 guards=GUARDS):
        self.control, self.candidate, self.clock = control, candidate, clock
        self.per_minute, self.steps, self.min_minutes = (
            per_minute, steps, min_minutes)
        self.rng, self.guards = random.Random(seed), guards

    def run(self, limit=480, check_every=5):
        step, in_step, next_id = 0, 0, 0
        cn, ct, everything, series = [], [], [], Series(self.clock)
        res = CanaryResult("held", self.steps[0], 0, "time limit", 0, 0)
        for minute in range(1, limit + 1):
            self.clock.sleep(60)
            share, in_step = self.steps[step], in_step + 1
            served = []
            for _ in range(self.per_minute):
                chat = make_chat(next_id, self.rng)
                next_id += 1
                if self.rng.random() < share:      # a canary chat
                    served.append(self.candidate.serve(chat))
                else:
                    ct.append(self.control.serve(chat))
            cn += served
            everything += served
            series.record(sum(o.failed for o in served), len(served))
            res.minutes, res.share = minute, share
            if in_step % check_every:
                continue
            why = burning(series) or next(
                (f"{g.name}: clearly worse" for g in self.guards
                 if verdict(g, cn, ct) == "worse"), None)
            if why:
                res.decision, res.reason = "rolled back", why
                break
            if in_step >= self.min_minutes and all(
                    verdict(g, cn, ct) == "ok" for g in self.guards):
                res.log.append((minute, share))   # this step held
                if step + 1 == len(self.steps):
                    res.decision, res.reason = "promoted", "all guards ok"
                    break
                step, in_step, cn, ct = step + 1, 0, [], []
        res.exposed = len(everything)
        res.unasked = sum(o.unasked for o in everything)
        res.failed = sum(o.failed for o in everything)
        return res


def budget_at_risk(share, minutes, per_minute, failure_rate):
    """Failed chats a faulty candidate can cause before it is stopped."""
    return round(share * minutes * per_minute * failure_rate)
