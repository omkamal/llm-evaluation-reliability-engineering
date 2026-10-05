"""The quarterly learning review, in numbers.

Findings come from incidents, near misses, game days and drills. A
near miss is something that could have hurt and did not this time.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Finding:
    source: str         # incident | near miss | game day | drill
    text: str
    owner: str
    due: str            # ISO date
    done: bool
    case: str           # the case, guard or drill that fails if it returns


def closed_share(findings):
    return sum(f.done for f in findings) / len(findings)


def overdue(findings, today):
    """[(finding, days late)] for open findings past their date."""
    return [(f, (today - date.fromisoformat(f.due)).days)
            for f in findings
            if not f.done and date.fromisoformat(f.due) < today]


def without_case(findings):
    return [f for f in findings if not f.case]


def mix(findings):
    """{source: count}, in the order first seen."""
    return dict(Counter(f.source for f in findings))
