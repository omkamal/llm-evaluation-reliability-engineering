"""Classify, back off with full jitter, honour Retry-After, respect a shared budget and a deadline."""
import random

from common.clock import SystemClock

RETRYABLE = {408, 429, 500, 502, 503, 504, 529}   # timeouts, throttling, transient server trouble
QUOTA_GONE = {"enforced_spend_limit_reached"}     # a 429 that no wait fixes: the spend cap is used up


def amplification(retries, layers):
    """Attempts that reach the provider for ONE request when every layer retries `retries` times."""
    return (retries + 1) ** layers


def call_with_retry(call, budget, deadline, *, clock=None, rng=random,
                    base=0.5, cap=8.0, tries=3, log=print, timed=False):
    """`call()` returns (status, retry_after) or (status, retry_after, error_code).
    `deadline` is a reading of `clock` (clock.now() + 20), never a bare 20.
    With timed=True each attempt is called as call(seconds_left), to use as its timeout."""
    if tries < 1 or not 0 < base <= cap:
        raise ValueError("need tries >= 1 and 0 < base <= cap")
    clock = clock or SystemClock()
    budget.record_request()
    for n in range(tries):
        left = deadline - clock.now()   # deadline: a reading of clock
        if left <= 0:
            return f"deadline passed before attempt {n + 1}"
        status, retry_after, *code = call(left) if timed else call()
        if status == 200:
            return f"ok on attempt {n + 1}"
        if status not in RETRYABLE or QUOTA_GONE & set(code):
            return f"{status}: not retryable"
        if n + 1 == tries:
            return f"{status}: giving up after {tries} attempts"
        window = min(cap, base * 2 ** n)
        sleep = (retry_after or 0) + rng.uniform(0, window)   # floor + jitter
        if clock.now() + sleep >= deadline:
            return f"{status}: no time left before the deadline"
        if not budget.allow_retry():            # asked last: a refusal costs nothing
            return f"{status}: retry budget is empty"
        log(f"  attempt {n + 1}: {status}, sleeping {sleep:.2f}s")
        clock.sleep(sleep)
