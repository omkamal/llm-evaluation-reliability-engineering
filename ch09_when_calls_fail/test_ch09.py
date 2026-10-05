"""Chapter 9 defences as tests. `pytest -q ch09_when_calls_fail`"""
import random

import pytest

from common.clock import FakeClock
from ch09_when_calls_fail.breaker import CircuitBreaker
from ch09_when_calls_fail.budget import RetryBudget, storm
from ch09_when_calls_fail.guard import BudgetExceeded, StepGuard
from ch09_when_calls_fail.loop_guard import LoopGuard
from ch09_when_calls_fail.quota import QuotaManager
from ch09_when_calls_fail.retry import amplification, call_with_retry


def scripted(*responses):
    it = iter(responses)
    return lambda: next(it)


def test_retries_multiply_across_layers():
    assert amplification(3, 3) == 64 and amplification(3, 1) == 4
    assert 1000 * amplification(3, 3) == 64_000


def test_non_retryable_errors_are_never_retried():
    clock = FakeClock()
    for status in (400, 401, 403):
        calls = []
        result = call_with_retry(lambda s=status: (calls.append(1), (s, None))[1], RetryBudget(), 99, clock=clock)
        assert "no retry" in result and len(calls) == 1 and clock.t == 0


def test_retry_after_is_a_floor_and_jitter_stays_in_the_window():
    clock = FakeClock()
    result = call_with_retry(scripted((429, 5.0), (200, None)), RetryBudget(), 60,
                             clock=clock, rng=random.Random(1), log=lambda *_: None)
    assert result == "ok on attempt 2" and clock.t >= 5.0
    for n in range(6):                                   # full jitter: 0 <= sleep <= min(cap, base * 2**n)
        assert 0 <= random.Random(n).uniform(0, min(8.0, 0.5 * 2 ** n)) <= min(8.0, 0.5 * 2 ** n)


def test_a_retry_that_cannot_finish_before_the_deadline_is_not_attempted():
    result = call_with_retry(scripted((429, 30.0), (200, None)), RetryBudget(), deadline=10,
                             clock=FakeClock(), log=lambda *_: None)
    assert "deadline" in result


def test_the_shared_budget_caps_retries_in_a_storm():
    assert storm(1000) == 104                            # the printed number in the chapter
    assert storm(1000) < 1000 * 2 / 10


def test_an_empty_budget_stops_retrying():
    budget = RetryBudget(burst=0.0)
    result = call_with_retry(scripted((503, None), (200, None)), budget, 99,
                             clock=FakeClock(), log=lambda *_: None)
    assert "giving up" in result


def test_breaker_opens_probes_and_closes():
    clock = FakeClock()
    br = CircuitBreaker(clock=clock)
    for _ in range(5):
        br.record(False)
    assert br.state == "open" and not br.allow()
    clock.sleep(30)
    assert [br.allow() for _ in range(4)] == [True, True, True, False] and br.state == "half_open"
    for _ in range(3):
        br.record(True)
    assert br.state == "closed"


def test_a_failed_probe_reopens_the_breaker():
    clock = FakeClock()
    br = CircuitBreaker(clock=clock)
    for _ in range(5):
        br.record(False)
    clock.sleep(30)
    assert br.allow()
    br.record(False)
    assert br.state == "open" and not br.allow()


def test_step_guard_stops_before_the_twelfth_step():
    guard = StepGuard(clock=FakeClock())
    with pytest.raises(BudgetExceeded, match="tokens"):
        while True:
            guard.before_step(3_500, 0.04)
    assert guard.used["steps"] == 11


def test_step_guard_also_enforces_time():
    clock = FakeClock()
    guard = StepGuard(clock=clock)
    clock.sleep(91)
    with pytest.raises(BudgetExceeded, match="seconds"):
        guard.before_step(10, 0.001)


def test_loop_guard_catches_the_fourth_identical_call():
    lg = LoopGuard()
    with pytest.raises(RuntimeError, match="loop"):
        for _ in range(10):
            lg.check("reschedule_delivery", {"tracking_id": "PP-2210"})
    assert lg.steps == 4


def test_quota_borrowing_stops_when_chats_are_waiting():
    q = QuotaManager()
    assert q.admit("background", 70_000) == "admit"      # chats are quiet: borrow the spare
    q.new_minute()
    q.chat_waiting = True
    assert q.admit("background", 30_000) == "admit"
    assert q.admit("background", 30_000) == "defer"
    assert q.admit("interactive", 40_000) == "admit"
    assert q.admit("interactive", 30_000) == "admit"     # the quota is now full
    assert q.admit("background", 10) == "shed"           # background is shed first
    assert q.admit("interactive", 10) == "wait"          # a chat waits; it is never shed
