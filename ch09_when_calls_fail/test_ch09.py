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
        assert "not retryable" in result and len(calls) == 1 and clock.t == 0


def test_retry_after_is_a_floor():
    clock = FakeClock()
    result = call_with_retry(scripted((429, 5.0), (200, None)), RetryBudget(), 60,
                             clock=clock, rng=random.Random(1), log=lambda *_: None)
    assert result == "ok on attempt 2" and clock.t >= 5.0


def test_a_retry_that_cannot_finish_before_the_deadline_is_not_attempted():
    result = call_with_retry(scripted((429, 30.0), (200, None)), RetryBudget(), deadline=10,
                             clock=FakeClock(), log=lambda *_: None)
    assert "deadline" in result


def test_the_shared_budget_caps_retries_in_a_storm():
    assert storm(1000) == 104                            # the printed number in the chapter
    assert storm(1000) < 1000 * 2 / 10


def test_an_empty_budget_stops_retrying():
    budget = RetryBudget()
    budget.tokens = 0.0                                  # drained by a storm
    budget.record_request = lambda: None
    result = call_with_retry(scripted((503, None), (200, None)), budget, 99,
                             clock=FakeClock(), log=lambda *_: None)
    assert "retry budget is empty" in result


def test_breaker_opens_probes_and_closes():
    clock = FakeClock()
    br = CircuitBreaker(clock=clock)
    for _ in range(5):
        br.record(False)
    assert br.state == "open" and not br.allow()
    clock.sleep(30)
    tickets = [br.allow() for _ in range(4)]
    assert tickets == ["probe", "probe", "probe", False] and br.state == "half_open"
    for t in tickets[:3]:
        br.record(True, t)
    assert br.state == "closed"


def test_a_failed_probe_reopens_the_breaker():
    clock = FakeClock()
    br = CircuitBreaker(clock=clock)
    for _ in range(5):
        br.record(False)
    clock.sleep(30)
    ticket = br.allow()
    br.record(False, ticket)
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


# ---- review fixes (October 2026): each test failed before its fix ----

class RecordingClock(FakeClock):
    def __init__(self, start=0.0):
        super().__init__(start)
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        super().sleep(seconds)


def quiet(**kw):
    return dict(log=lambda *_: None, **kw)


def test_a_504_gateway_timeout_is_retried():
    result = call_with_retry(scripted((504, None), (200, None)), RetryBudget(),
                             20, **quiet(clock=FakeClock()))
    assert result == "ok on attempt 2"


def test_a_spend_cap_429_is_never_retried():
    calls = []

    def spend_cap():
        calls.append(1)
        return 429, None, "enforced_spend_limit_reached"
    result = call_with_retry(spend_cap, RetryBudget(), 20, **quiet(clock=FakeClock()))
    assert len(calls) == 1 and "not retryable" in result


def test_one_retry_layer_makes_at_most_three_attempts():
    calls = []
    call_with_retry(lambda: (calls.append(1), (503, None))[1], RetryBudget(), 60,
                    **quiet(clock=FakeClock()))
    assert len(calls) == 3                      # tries=3: two retries


def test_the_deadline_is_a_reading_of_the_same_clock():
    clock = FakeClock(start=92_511.0)           # a monotonic clock is never near 0
    ok = call_with_retry(scripted((503, None), (200, None)), RetryBudget(),
                         clock.now() + 20, **quiet(clock=clock))
    assert ok == "ok on attempt 2"
    calls = []
    late = call_with_retry(lambda: (calls.append(1), (200, None))[1], RetryBudget(),
                           20, **quiet(clock=clock))      # the bare number 20 is long past
    assert calls == [] and "deadline" in late


def test_each_attempt_is_given_the_time_that_is_left():
    clock, seen = FakeClock(), []

    def slow(left):                             # a call that obeys its timeout
        seen.append(left)
        clock.sleep(min(6, left))               # each attempt wants 6 s
        return (503, None) if left > 6 else (408, None)
    result = call_with_retry(slow, RetryBudget(), 20, timed=True,
                             **quiet(clock=clock, rng=random.Random(3), tries=5))
    assert seen[0] == 20 and all(b < a for a, b in zip(seen, seen[1:]))
    assert clock.now() <= 20 + 1e-9 and "deadline" in result


def test_jitter_is_added_on_top_of_retry_after():
    sleeps = []
    for seed in range(1000):                    # a thousand clients, all told "1 s"
        clock = RecordingClock()
        call_with_retry(scripted((429, 1.0), (200, None)), RetryBudget(), 20,
                        **quiet(clock=clock, rng=random.Random(seed)))
        sleeps += clock.sleeps
    assert min(sleeps) >= 1.0                   # the floor still holds
    assert max(sleeps) - min(sleeps) > 0.4      # but the clients spread out
    assert len({round(s, 2) for s in sleeps}) > 40


def test_the_sleep_the_loop_chooses_stays_in_the_jitter_window():
    for seed in range(200):
        clock = RecordingClock()
        call_with_retry(lambda: (503, None), RetryBudget(), 60,
                        **quiet(clock=clock, rng=random.Random(seed), tries=6))
        for n, s in enumerate(clock.sleeps):
            assert 0 <= s <= min(8.0, 0.5 * 2 ** n)


def test_a_retry_refused_for_lack_of_time_costs_no_retry_budget():
    budget = RetryBudget()
    call_with_retry(scripted((429, 30.0), (200, None)), budget, 10,
                    **quiet(clock=FakeClock()))
    assert budget.tokens == 5.0


def test_retry_settings_that_cannot_work_are_refused():
    with pytest.raises(ValueError):
        RetryBudget(burst=0.5)                  # can never hold a whole token
    for bad in (dict(tries=0), dict(cap=-1.0), dict(base=0.0)):
        with pytest.raises(ValueError):
            call_with_retry(lambda: (200, None), RetryBudget(), 20,
                            **quiet(clock=FakeClock(), **bad))


def tripped(clock):
    br = CircuitBreaker(clock=clock)
    for _ in range(5):
        br.record(False)
    return br


def test_silent_probes_do_not_lock_the_provider_out():
    clock = FakeClock()
    br = tripped(clock)
    clock.sleep(30)
    assert all(br.allow() for _ in range(3))   # three probes, never reported
    clock.sleep(30)
    assert not br.allow() and br.state == "open"    # silence counts as failure
    clock.sleep(30)
    assert br.allow() == "probe"                # a fresh round of probes


def test_late_successes_from_before_the_trip_do_not_close_the_breaker():
    clock = FakeClock()
    br = tripped(clock)
    clock.sleep(30)
    ticket = br.allow()                         # one probe goes out
    for _ in range(3):
        br.record(True)                         # calls admitted while closed
    assert br.state == "half_open"
    br.record(True, ticket)
    assert br.state == "half_open"              # one probe is not three
    for t in (br.allow(), br.allow()):
        br.record(True, t)
    assert br.state == "closed"


def test_breaker_settings_that_cannot_close_are_refused():
    with pytest.raises(ValueError):
        CircuitBreaker(probes=0)


class PausingUsed(dict):
    """Pause each thread between the guard's check and its reservation."""
    def __init__(self, used, barrier):
        super().__init__(used)
        self.barrier, self.paused = barrier, set()

    def __getitem__(self, key):
        import threading
        me = threading.get_ident()
        if key == "seconds" and me not in self.paused:
            self.paused.add(me)
            try:
                self.barrier.wait()
            except threading.BrokenBarrierError:
                pass
        return super().__getitem__(key)


def test_two_threads_cannot_both_take_the_last_step():
    import threading
    guard = StepGuard(steps=1, clock=FakeClock())
    guard.used = PausingUsed(guard.used, threading.Barrier(2, timeout=0.5))
    admitted = []

    def step():
        try:
            guard.before_step(100, 0.01)
            admitted.append(1)
        except BudgetExceeded:
            pass
    threads = [threading.Thread(target=step) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(admitted) == 1


def test_money_limits_are_not_broken_by_float_rounding():
    guard = StepGuard(usd=0.30, clock=FakeClock())
    with pytest.raises(BudgetExceeded, match="usd"):
        while True:
            guard.before_step(10, 0.10)
    assert guard.used["steps"] == 3            # 0.1 + 0.1 + 0.1 is not > 0.30


def test_step_budgets_are_per_task_so_long_sessions_survive():
    clock = FakeClock()
    for turn in range(20):                      # a 20-turn session (Chapter 14)
        guard = StepGuard(clock=clock)          # one guard per task
        for _ in range(3):                      # each task: three agent steps
            guard.before_step(3_500, 0.04)
            clock.sleep(2)
    assert clock.now() == 120                   # never stopped


def test_loop_guard_accepts_tool_arguments_that_hold_lists():
    lg = LoopGuard()
    for _ in range(3):
        lg.check("lookup_order", {"ids": ["a", "b"]})
    with pytest.raises(RuntimeError, match="loop"):
        lg.check("lookup_order", {"ids": ["a", "b"]})


def test_the_chat_reserve_is_still_there_after_background_borrowed():
    q = QuotaManager()
    assert q.admit("background", 90_000) == "defer"     # never the held share
    assert q.admit("background", 60_000) == "admit"     # borrows while quiet
    q.chat_waiting = True
    assert q.admit("background", 1_000) == "defer"      # borrowing stops
    assert q.admit("interactive", 30_000) == "admit"    # the held share is there
