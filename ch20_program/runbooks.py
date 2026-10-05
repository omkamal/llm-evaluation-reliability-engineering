"""Runbooks that get used: short, linked from the alert, and drilled.

A runbook nobody has run since it was written is a guess in a nice
font. These checks catch the ways it goes stale.
"""
from dataclasses import dataclass
from datetime import date

ONE_SCREEN = 30       # lines
A_QUARTER = 90        # days between drills


@dataclass(frozen=True)
class Runbook:
    name: str
    author: str
    lines: int
    last_drilled: str       # ISO date, or "" if never
    drilled_by: str         # who ran it for real, or ""


def problems(book, today):
    out = []
    if book.lines > ONE_SCREEN:
        out.append(f"{book.lines} lines (one screen is {ONE_SCREEN})")
    if not book.last_drilled:
        out.append("never drilled")
    else:
        age = (today - date.fromisoformat(book.last_drilled)).days
        if age > A_QUARTER:
            out.append(f"not drilled for {age} days")
        if book.drilled_by == book.author:
            out.append("drilled only by its author")
    return out


def audit(page_alerts, books, today):
    """Check every page alert. Returns (findings, sound alerts, total)."""
    by_name = {b.name: b for b in books}
    findings, sound = [], 0
    for alert, link in page_alerts.items():
        if not link:
            findings.append(f"{alert}: no runbook linked")
        elif link not in by_name:
            findings.append(f"{alert}: {link} does not exist")
        else:
            bad = problems(by_name[link], today)
            findings += [f"{alert}: {link}: {why}" for why in bad]
            sound += not bad
    return findings, sound, len(page_alerts)
