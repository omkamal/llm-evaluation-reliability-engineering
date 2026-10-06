"""An inventory of what runs, and change control for what changes.

If it is not on the list, nobody owns it; if nobody owns it, nobody
reviews it. The list is checked against what is really running.
"""
from dataclasses import dataclass, replace
from datetime import date

KINDS = ("agent", "tool", "prompt", "model", "index", "policy")


@dataclass(frozen=True)
class Item:
    kind: str
    name: str
    version: str
    owner: str               # a person or a team that answers for it
    reviewed: str            # ISO date of the last review


def audit_inventory(items, running, today, max_age_days=90):
    """Findings: things running unlisted, unowned or long unreviewed."""
    listed = {(i.kind, i.name, i.version) for i in items}
    found = [f"running, not listed: {k} {n} {v}"
             for k, n, v in sorted(running) if (k, n, v) not in listed]
    for item in items:
        if not item.owner:
            found.append(f"no owner: {item.kind} {item.name}")
        age = (today - date.fromisoformat(item.reviewed)).days
        if age > max_age_days:
            found.append(f"unreviewed for {age} days: "
                         f"{item.kind} {item.name}")
    return found


@dataclass
class Change:
    kind: str
    name: str
    new_version: str
    why: str
    author: str
    approver: str
    eval_run: str            # id of the eval run that passed (Chapter 15)


def second_pair(approver, author):
    """Someone, and someone else: "Sam" may not approve "sam"."""
    who = approver.strip().lower()
    return bool(who) and who != author.strip().lower()


def apply_change(items, change, log, today):
    """Return the new inventory, or raise: no why, no gate, no 2nd pair
    of eyes, no change. Every applied change leaves an audit record."""
    if not change.why.strip():
        raise ValueError("a change needs a reason")
    if not change.eval_run:
        raise ValueError("a change needs a passing eval run")
    if not second_pair(change.approver, change.author):
        raise ValueError("the approver must be someone else")
    out, hit = [], False
    for item in items:
        if (item.kind, item.name) == (change.kind, change.name):
            item = replace(item, version=change.new_version,
                           reviewed=today.isoformat())
            hit = True
        out.append(item)
    if not hit:
        raise ValueError(f"{change.kind} {change.name} is not listed")
    log.record(agent=change.author, version="-", tool="change",
               args={"item": f"{change.kind}:{change.name}",
                     "to": change.new_version, "eval": change.eval_run},
               decision="allow", approver=change.approver,
               trace="-", task=change.why)
    return out
