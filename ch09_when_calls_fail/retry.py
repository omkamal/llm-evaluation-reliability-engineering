"""Classify, back off with full jitter, honour Retry-After, respect a shared budget and a deadline."""
import random

from common.clock import SystemClock

RETRYABLE = {408, 429, 500, 502, 503, 529}   # timeouts, throttling, transient server trouble


def amplification(retries, layers):
    """Attempts that reach the provider for ONE request when every layer retries `retries` times."""
    return (retries + 1) ** layers


def call_with_retry(call, budget, deadline, *, clock=None, rng=random,
                    base=0.5, cap=8.0, tries=3, log=print):
    clock = clock or SystemClock()
    budget.record_request()
    for n in range(tries):
        status, retry_after = call()
        if status == 200:
            return f"ok on attempt {n + 1}"
        if status not in RETRYABLE:
            return f"{status}: fix or hand off, no retry"
        if n + 1 == tries or not budget.allow_retry():
            return f"{status}: giving up (tries or budget)"
        sleep = rng.uniform(0, min(cap, base * 2 ** n))   # full jitter
        sleep = max(sleep, retry_after or 0)   # Retry-After is a floor
        if clock.now() + sleep > deadline:
            return f"{status}: no time left before the deadline"
        log(f"  attempt {n + 1}: {status}, sleeping {sleep:.2f}s")
        clock.sleep(sleep)
