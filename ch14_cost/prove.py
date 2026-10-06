"""Prove a saving without losing quality: a paired comparison.

Both policies run on the SAME cases (Chapter 4), so each case keeps
its two outcomes together and the interval is narrower.
"""
from dataclasses import dataclass

from ch04_numbers.stats import paired_bootstrap
from ch12_slos.tasks import cost_per_resolved

MARGIN = 0.02     # the most resolved rate we will give up: 2 points


@dataclass(frozen=True)
class Verdict:
    saving: float       # fall in cost per resolved task
    change: float       # change in resolved rate
    low: float          # lower end of its 95% interval
    high: float
    ship: bool


def compare(base, cand, margin=MARGIN, seed=1):
    """base and cand: Task lists for the same cases in the same order."""
    saving = 1 - cost_per_resolved(cand) / cost_per_resolved(base)
    change, (low, high) = paired_bootstrap(
        [int(t.resolved) for t in base], [int(t.resolved) for t in cand],
        resamples=4000, seed=seed)
    # ship only if even the worst end of the interval is inside the margin
    return Verdict(saving, change, low, high, low > -margin)
