"""Capacity: how many calls are in flight, and what does headroom buy?"""
import heapq
from math import log
import random

from ch12_slos.tasks import percentile


def in_flight(per_minute, seconds):
    """Little's law: calls in flight = arrival rate x time each takes."""
    return per_minute / 60 * seconds


def load_test(slots, seconds, per_minute, minutes=10, deadline=20.0,
              seed=3):
    """Poisson arrivals at a provider that serves `slots` calls at once.

    Returns (p95 latency in seconds, share that missed the deadline).
    A request that would wait past the deadline is dropped, as a 429
    or a timeout would drop it.
    """
    rng = random.Random(seed)
    free = [0.0] * slots                 # when each slot is next free
    heapq.heapify(free)
    t, latencies, dropped, total = 0.0, [], 0, 0
    while t < minutes * 60:
        t += rng.expovariate(per_minute / 60)
        total += 1
        wait = max(0.0, free[0] - t)
        if wait > deadline:
            dropped += 1
            continue
        # a long tail, scaled so that the mean is `seconds`
        service = rng.lognormvariate(log(seconds) - 0.18, 0.6)
        heapq.heapreplace(free, t + wait + service)
        latencies.append(wait + service)
    return percentile(latencies, 95), dropped / total


def hourly_cost(demand, committed, b):
    """One hour: committed capacity is paid for whether used or not.

    demand and committed are in tokens per minute. Capacity used in full
    would cost b (a share of the on-demand price); demand above the
    commitment is billed on demand at 1.0.
    """
    return b * committed + max(0.0, demand - committed)


def day_cost(profile, committed, b):
    return sum(hourly_cost(d, committed, b) for d in profile)


def best_commitment(profile, b, step=10):
    """The commitment (tokens per minute) with the lowest day cost."""
    levels = range(0, int(max(profile)) + step, step)
    return min(levels, key=lambda c: day_cost(profile, c, b))
