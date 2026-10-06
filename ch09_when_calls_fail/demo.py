"""Every Chapter 9 defence, with its printed output.   python3 -m ch09_when_calls_fail.demo"""
import random

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


def main():
    print("== amplification")
    print(f"3 retries at 3 layers = {amplification(3, 3)} calls per message")
    print(f"1,000 chats/min -> {1000 * amplification(3, 3):,} calls/min")

    print("== classify, back off, honour Retry-After")
    clock, rng = FakeClock(), random.Random(7)
    for script in (scripted((429, 1.0), (503, None), (200, None)), scripted((400, None)),
                   scripted((429, None, "enforced_spend_limit_reached"))):
        print(call_with_retry(script, RetryBudget(), deadline=clock.now() + 20, clock=clock, rng=rng))

    print("== shared retry budget")
    print(f"with a budget: {storm(1000)} retries for 1000 requests")
    print(f"3 tries each, no budget: {1000 * (3 - 1)} retries")

    print("== circuit breaker")
    clock = FakeClock()
    br = CircuitBreaker(clock=clock)
    for _ in range(5):
        br.record(False)
    print(f"after 5 failures: {br.state} | next call allowed? {br.allow()}")
    clock.sleep(30)
    tickets = [br.allow() for _ in range(4)]
    print(f"after cooldown, 4 callers: {tickets} {br.state}")
    states = []
    for ticket in tickets[:3]:
        br.record(True, ticket)
        states.append(br.state)
    print("probe successes: " + " -> ".join(states))

    print("== step guard")
    guard = StepGuard(clock=FakeClock())
    try:
        while True:                             # the overnight loop: a failing tool, an agent that keeps trying
            guard.before_step(est_tokens=3_500, est_usd=0.04)
    except BudgetExceeded as why:
        print(f"stopped safely after {guard.used['steps']} steps ({why})")

    print("== loop guard")
    lg = LoopGuard()
    try:
        while True:
            lg.check("reschedule_delivery", {"tracking_id": "PP-2210", "new_date": "2026-12-23"})
    except RuntimeError as err:
        print(f"aborted at step {lg.steps}: {err}")

    print("== quota manager")
    q = QuotaManager()                          # one minute, no reset in between
    print("quiet chats, background borrows:", q.admit("background", 60_000), q.admit("background", 20_000))
    q.chat_waiting = True
    print("chats waiting, background stops:", q.admit("background", 1_000))
    print("chats still admitted:", q.admit("interactive", 40_000))


if __name__ == "__main__":
    main()
