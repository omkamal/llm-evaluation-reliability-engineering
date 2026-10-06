"""Measure the loop: hand-offs, overrides, waiting, agreement."""
from math import ceil

from ch05_judge.agreement import cohen_kappa


def nearest_rank(values, q):
    """The q-th percentile (0 to 1) by the nearest-rank rule."""
    ordered = sorted(values)
    return ordered[max(0, ceil(q * len(ordered)) - 1)]


def loop_metrics(outcomes, tasks, sla):
    """The numbers a review loop should report every week."""
    waits = [o.waited for o in outcomes]
    changed = sum(o.decision != "approve" for o in outcomes)
    return {
        "hand-off rate": len(outcomes) / tasks,
        "override rate": changed / len(outcomes),
        "queue p50 s": nearest_rank(waits, 0.5),
        "queue p95 s": nearest_rank(waits, 0.95),
        "past SLA": sum(w > sla for w in waits) / len(waits),
    }


def reviewer_agreement(first, second):
    """Kappa between two reviewers on the same double-checked cases."""
    return cohen_kappa(first, second)
