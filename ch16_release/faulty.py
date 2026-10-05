"""Rehearse failure: a provider that breaks on purpose, on virtual time.

`FaultyProvider` is Chapter 10's scripted provider with dice: each call
may rate-limit, stall, cut its stream, return broken JSON or run slow.
The defences are the ones Chapters 2, 9 and 10 built; the clock is
Chapter 10's `VirtualClock`, so 2,000 chats take no real time.
"""
import random
from collections import deque
from dataclasses import dataclass, field

from ch09_when_calls_fail.budget import RetryBudget
from ch10_providers.fakes import FULL, stream
from ch10_providers.stream import consume
from ch10_providers.vtime import VirtualClock

# the menu, one slice of the dice each (the order matters)
FAULTS = {"rate_limited": 0.05, "timeout": 0.02,
          "stream_cut": 0.03, "bad_json": 0.02}
BACKUP_FAULTS = {"rate_limited": 0.01, "timeout": 0.01}
TARGET = 0.995                 # the steady-state hypothesis: availability
FIRST_TOKEN_S = 0.8            # a healthy call's first token
SLOW_S = 2.5                   # what a slow call adds
BAD_JSON = [e for e in FULL if e[0] != "tool_delta"][:-1] + [
    ("tool_delta", '{"order_id": "ORD-004830", "amount_cents"'),
    ("stop", "tool")]            # a stop event, yet unusable JSON


class RateLimited(Exception):
    """An HTTP 429: it arrives before any stream starts."""


class FaultyProvider:
    def __init__(self, clock, faults, seed, slow=0.0):
        self.clock, self.faults, self.slow = clock, faults, slow
        self.dice = random.Random(seed)          # which fault, if any
        self.lag = random.Random(seed + 1)       # separate: latency only
        self.injected = {name: 0 for name in faults}
        self.first_tokens = []                   # when text first arrived

    def roll(self):
        roll = self.dice.random()
        for name, chance in self.faults.items():
            if roll < chance:
                self.injected[name] += 1
                return name
            roll -= chance
        return None

    async def chat(self):
        """One call: a StreamResult, or RateLimited."""
        fault = self.roll()
        if fault == "rate_limited":
            raise RateLimited()
        extra = SLOW_S if self.lag.random() < self.slow else 0.0
        await self.clock.sleep(FIRST_TOKEN_S + extra)
        if fault != "timeout":                   # a stall never speaks
            self.first_tokens.append(self.clock.now())
        events = BAD_JSON if fault == "bad_json" else FULL
        cut = 7 if fault == "stream_cut" else None
        quiet = 0 if fault == "timeout" else None   # open, then silent
        return await consume(stream(events, self.clock, cut_after=cut,
                                    stall_after=quiet), lambda s: None,
                             self.clock)


@dataclass
class Run:
    chats: int = 0
    failed: list = field(default_factory=list)       # chat numbers
    quick: int = 0                                   # first token in 2 s
    ran_from_partial: int = 0
    injected: dict = field(default_factory=dict)
    aborted: str = ""

    @property
    def availability(self):
        return 1 - len(self.failed) / self.chats

    @property
    def first_token_rate(self):
        return self.quick / self.chats

    @property
    def holds(self):
        return self.availability >= TARGET and self.ran_from_partial == 0


async def attempt(provider):
    """'ok', 'retry' (transient), 'cut' or 'bad_json'."""
    try:
        res = await provider.chat()
    except RateLimited:
        return "retry"
    if res.status == "complete":
        return "ok"
    return {"stalled": "retry", "cut": "cut"}.get(res.why, res.why)


def run_experiment(n=2000, failover=False, seed=7, faults=FAULTS,
                   slow=0.02, abort_below=None):
    """Send `n` chats through Relay's defences with faults injected."""
    clock = VirtualClock()
    primary = FaultyProvider(clock, faults, seed, slow)
    backup = FaultyProvider(clock, BACKUP_FAULTS, seed + 4)
    budget, run = RetryBudget(), Run()

    async def with_retry():
        for tries in range(3):
            got = await attempt(primary)
            if got != "retry":
                return got
            if tries == 2 or budget.tokens < 1:
                break                         # out of tries or budget
            budget.tokens -= 1
        if failover:                          # the fix run 1 pointed to
            got = await attempt(backup)
            return None if got == "retry" else got
        return None

    async def chat():
        budget.record_request()
        got = await with_retry()
        if got == "cut":                      # the partial call is dropped
            got = await with_retry() if budget.tokens >= 1 else None
            got = None if got == "cut" else got
        return got is not None                # bad JSON: repaired once

    async def main():
        recent = deque(maxlen=50)
        for i in range(1, n + 1):
            started, seen = clock.now(), len(primary.first_tokens)
            seen_b = len(backup.first_tokens)
            ok = await chat()
            run.chats = i
            if not ok:
                run.failed.append(i)
            firsts = (primary.first_tokens[seen:]
                      + backup.first_tokens[seen_b:])
            run.quick += bool(firsts) and min(firsts) - started <= 2.0
            recent.append(ok)
            if (abort_below and len(recent) == 50
                    and sum(recent) / 50 < abort_below):
                run.aborted = (f"availability {sum(recent) / 50:.0%} "
                               "over the last 50 chats")
                return                         # the stop condition

    clock.run(main())
    run.injected = dict(primary.injected)
    return run
