"""A blameless postmortem as a record that can be checked.

There is no field for a culprit. Contributing factors are filed by
phase, and every action item needs an owner, a date and a regression
case: an eval case, a guardrail test or a drill that fails if the
problem comes back."""
from dataclasses import dataclass, field
from datetime import date

PHASES = ("prevent", "detect", "contain")


@dataclass
class Factor:
    phase: str          # prevent | detect | contain
    text: str


@dataclass
class ActionItem:
    text: str
    owner: str = ""
    due: str = ""       # ISO date, "2026-09-24"
    case: str = ""      # the regression case that guards it
    done: bool = False


@dataclass
class Postmortem:
    incident: str
    happened: str       # ISO date
    factors: list = field(default_factory=list)
    actions: list = field(default_factory=list)


def _iso(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def problems(pm, today, people=()):
    """Everything a reviewer would send back. `today` is passed in.
    Owners may be named; contributing factors may not."""
    out = []
    for phase in PHASES:
        if not any(f.phase == phase for f in pm.factors):
            out.append(f"no contributing factor about '{phase}'")
    for f in pm.factors:
        if any(p in f.text for p in people):
            out.append(f"'{f.text}': names a person")
    for a in pm.actions:
        due = _iso(a.due)
        if not a.owner:
            out.append(f"'{a.text}': no owner")
        if due is None:
            out.append(f"'{a.text}': no date")
        elif due < _iso(pm.happened):
            out.append(f"'{a.text}': due before the incident")
        elif not a.done and due < today:
            out.append(f"'{a.text}': overdue")
        if not a.case:
            out.append(f"'{a.text}': no regression case")
    return out


def closed_share(pm):
    """Share of action items done: the number to put on a dashboard."""
    return sum(a.done for a in pm.actions) / len(pm.actions)


def cases_added(pm):
    """Distinct regression cases this incident left behind (an item
    may name several, separated by spaces)."""
    return len({c for a in pm.actions for c in a.case.split()})
