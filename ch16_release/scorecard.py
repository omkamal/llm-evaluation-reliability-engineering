"""A model-selection scorecard: hard limits first, then cost per resolved task.

Every number is invented for the book, on an invented eval set of 200
cases. Prices are illustrative and different for every model; replace
all of it with your own measurements.
"""
from dataclasses import dataclass

from ch04_numbers.stats import proportion_ci

CASES = 200                       # the eval set: ours, not a benchmark
LIMITS = {"floor": 0.90,          # quality: baseline 0.91 minus 1 point
          "p95_first_token": 2.0, # seconds, from our own traffic
          "months_left": 9,       # before the provider retires it
          "retention_days": 30}   # how long our data may be kept


@dataclass(frozen=True)
class Candidate:
    name: str
    passed: int             # cases passed out of CASES
    usd_per_task: float     # all-in, at our volume
    p95_first_token: float
    months_left: int        # until its published retirement
    retention_days: int     # terms: how long it keeps our data


def api_cost(usd_per_mtok, tokens):
    """Dollars per task for a model billed by the token."""
    return usd_per_mtok * tokens / 1_000_000


def self_hosted_cost(fixed_monthly, marginal, tasks_per_month):
    """Dollars per task when we run it: the fixed bill spread thin."""
    return fixed_monthly / tasks_per_month + marginal


def breakeven_tasks(fixed_monthly, api_per_task, own_marginal):
    """Monthly tasks above which running it ourselves is cheaper."""
    return fixed_monthly / (api_per_task - own_marginal)


def out_reasons(c, limits=LIMITS):
    """Which hard limits this candidate breaks (empty: it is eligible)."""
    why = []
    if c.passed / CASES < limits["floor"]:
        why.append("quality")
    if c.p95_first_token > limits["p95_first_token"]:
        why.append("latency")
    if c.months_left < limits["months_left"]:
        why.append("life")
    if c.retention_days > limits["retention_days"]:
        why.append("terms")
    return why


def per_resolved(c):
    """Cost per resolved task: everything spent over tasks that worked."""
    return c.usd_per_task / (c.passed / CASES)


def choose(candidates):
    """The cheapest eligible candidate per resolved task, or None."""
    ok = [c for c in candidates if not out_reasons(c)]
    return min(ok, key=per_resolved) if ok else None


def table(candidates):
    lines = []
    for c in candidates:
        p, _, (lo, hi) = proportion_ci(c.passed, CASES)
        why = out_reasons(c)
        lines.append(f"{c.name:<20}{p:>5.2f} {lo:.2f} to {hi:.2f}"
                     f"  ${per_resolved(c):.4f}  "
                     + ("out: " + ", ".join(why) if why else "eligible"))
    return lines
