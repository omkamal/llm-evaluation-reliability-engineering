"""FinOps in small pieces: unit cost, a forecast, a month-end check."""
from dataclasses import dataclass

from ch14_cost.economics import CALLS_PER_TASK, PREFIX, REPLY
from ch14_cost.prices import call_usd

DAYS = 30


def monthly_bill(tasks, share_small=0.0, calls=CALLS_PER_TASK):
    """Forecast from traffic AND tokens per task, split by tier."""
    big = call_usd("frontier", PREFIX, REPLY)
    small = call_usd("small", PREFIX, REPLY)
    per_call = (1 - share_small) * big + share_small * small
    return tasks * calls * per_call


def forecast_miss(bill, growth, invoice):
    """What a traffic-only forecast predicts, and how far off it is."""
    predicted = bill * (1 + growth)
    return predicted, invoice - predicted


def projection(spent, day, days=DAYS):
    """Month-end spend if the rest of the month looks like so far."""
    return spent / day * days


def status(spent, day, cost_budget, days=DAYS):
    """Is a team on course for its monthly cost budget?"""
    expected = projection(spent, day, days)
    if expected > cost_budget:
        return f"over by {expected / cost_budget - 1:.0%}"
    return "on course"


@dataclass(frozen=True)
class Record:
    """One task, tagged where it is made (the gateway adds the tags)."""
    team: str
    tenant: str
    usd: float
    resolved: bool


def showback(records, by):
    """{key: (tasks, spend, cost per resolved task)} by team or tenant."""
    groups = {}
    for r in records:
        groups.setdefault(getattr(r, by), []).append(r)
    out = {}
    for key, g in sorted(groups.items()):
        spend = sum(r.usd for r in g)
        done = sum(r.resolved for r in g)
        out[key] = (len(g), spend, spend / max(1, done))
    return out
