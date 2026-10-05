"""Shallow and deep health checks for one dependency."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Dependency:
    name: str
    answers: bool           # does it respond at all? (a shallow check)
    result: str             # what a tiny real task returned
    expect: str             # a fact a right result must contain


def shallow(dep):
    """Are you alive?"""
    return dep.answers


def deep(dep):
    """Can you do the job? Run a synthetic task, check the result."""
    return dep.answers and dep.expect in dep.result


def health_table(deps):
    rows = []
    for d in deps:
        s = "ok" if shallow(d) else "FAIL"
        t = "ok" if deep(d) else "FAIL"
        rows.append(f"{d.name:<16}{s:<9}{t}")
    return rows
