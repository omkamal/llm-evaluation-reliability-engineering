"""Golden signals per task, not per call. An illustrative simulation.

Every number here is invented: prices, step counts and timings stand in
for what your own traces would give you (Chapter 11).
"""
import random
from dataclasses import dataclass
from math import ceil

MODEL_CALL_USD = 0.008      # invented: one model call, tokens priced in


@dataclass(frozen=True)
class Call:
    task_id: int
    kind: str                       # "model" or "tool"
    seconds: float
    usd: float


@dataclass(frozen=True)
class Task:
    seconds: float                  # what the customer waits for
    usd: float                      # what the run cost, success or not
    resolved: bool


def simulate_calls(tasks=2000, seed=12):
    """Calls plus a verdict per task. Steps run one after another."""
    rng = random.Random(seed)
    calls, resolved = [], {}
    for task_id in range(tasks):
        for _ in range(rng.randint(2, 5)):
            secs = rng.uniform(0.6, 2.0)
            calls.append(Call(task_id, "model", secs, MODEL_CALL_USD))
        for _ in range(rng.randint(1, 3)):
            secs = rng.uniform(0.2, 1.0)
            calls.append(Call(task_id, "tool", secs, 0.0))
        resolved[task_id] = rng.random() < 0.992
    return calls, resolved


def per_task(calls, resolved):
    """Fold calls into tasks by task id: the unit the customer feels."""
    seconds, usd = {}, {}
    for c in calls:
        seconds[c.task_id] = seconds.get(c.task_id, 0.0) + c.seconds
        usd[c.task_id] = usd.get(c.task_id, 0.0) + c.usd
    return [Task(seconds[t], usd[t], resolved[t])
            for t in sorted(resolved)]


def percentile(values, q):
    """Nearest-rank percentile: q in 0 to 100."""
    ordered = sorted(values)
    return ordered[max(0, ceil(q / 100 * len(ordered)) - 1)]


def share_within(values, limit):
    """Share of values at or under the limit."""
    return sum(v <= limit for v in values) / len(values)


def cost_per_resolved(tasks):
    """All spend, failed tasks included, over tasks that were resolved."""
    return sum(t.usd for t in tasks) / sum(t.resolved for t in tasks)
