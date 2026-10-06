"""A production-readiness review that returns one of three answers.

launch                    every answer is a fresh yes
launch with named risks   some answers are partly, each with a risk, an
                          owner on the roster and a number of days (at
                          most a quarter) to close it
not yet                   a blocker is not a fresh yes, an answer is no,
                          or a risk has no name, owner or date

An answer older than a quarter drops a grade (a yes becomes a partly, a
partly a no), and evidence dated after today counts as no evidence.
The long checklist is Appendix A; this one fits on a card.
"""
from dataclasses import dataclass
from datetime import date

MAX_AGE = 90        # days: evidence older than a quarter is not evidence
STATUSES = ("yes", "partly", "no")


@dataclass(frozen=True)
class Question:
    key: str
    ask: str
    chapters: str
    blocker: bool = False


@dataclass(frozen=True)
class Answer:
    status: str             # "yes", "partly" or "no"
    evidence: str = ""      # ISO date someone last looked or ran it
    risk: str = ""          # what is left uncovered, in one sentence
    owner: str = ""         # one person on the roster, not "the team"
    days: int = 0           # days from now to close it


QUESTIONS = (
    Question("gate", "evals with a gate that blocks a regression",
             "3, 15", blocker=True),
    Question("slo", "a signed SLO sheet with burn-rate pages", "12"),
    Question("trace", "one conversation can be read step by step", "11"),
    Question("cost", "cost per resolved task, with a cost budget", "14"),
    Question("failover", "provider loss survived and rehearsed",
             "10, 16"),
    Question("guard", "a deterministic check before every tier 2 tool",
             "17", blocker=True),
    Question("creds", "scoped, short-lived, capped credentials", "18"),
    Question("review", "a person decides above the expected-loss line",
             "18"),
    Question("kill", "kill switch and pin, drilled this quarter", "19",
             blocker=True),
    Question("runbooks", "every page alert reaches a sound runbook",
             "19, 20"),
    Question("data", "data terms and retention read and dated", "10, 18"),
)


def standing(answer, today):
    """What an answer is worth today. An old answer drops a grade."""
    if answer is None:
        return "no", "no answer"
    if answer.status not in STATUSES:
        raise ValueError(f"status must be yes, partly or no: "
                         f"{answer.status!r}")
    if answer.status == "no":
        return "no", ""
    age = (today - date.fromisoformat(answer.evidence)).days
    if age < 0:
        return "no", "evidence is dated after today"
    if age > MAX_AGE:
        lower = "partly" if answer.status == "yes" else "no"
        return lower, f"evidence is {age} days old"
    return answer.status, ""


def review(questions, answers, today, roster):
    """(verdict, reasons). `roster` is Chapter 20's list of people: a
    risk owner must be on it and must not have left."""
    here = {p.name for p in roster if not p.left}
    stop, named = [], []
    for q in questions:
        a = answers.get(q.key)
        status, note = standing(a, today)
        if status == "yes":
            continue
        what = f"{q.key}: {status}" + (f", {note}" if note else "")
        if status == "no" or q.blocker:
            stop.append(what)
        elif a.risk and a.owner in here and 0 < a.days <= MAX_AGE:
            named.append(f"{what}; {a.risk}; {a.owner}, {a.days} days")
        else:
            stop.append(f"{what}; the risk has no name, owner or date")
    if stop:
        return "not yet", stop
    if named:
        return "launch with named risks", named
    return "launch", []
