"""A production-readiness review that returns one of three answers.

launch                    every answer is a fresh yes
launch with named risks   some answers are partly, each with a risk, an
                          owner and a number of days to close it
not yet                   a blocker is not a fresh yes, an answer is no,
                          or a risk has no name, owner or date

The long checklist is Appendix A; this one fits on a card.
"""
from dataclasses import dataclass
from datetime import date

MAX_AGE = 90        # days: evidence older than a quarter is not evidence


@dataclass(frozen=True)
class Question:
    key: str
    ask: str
    chapters: str
    blocker: bool = False


@dataclass(frozen=True)
class Answer:
    status: str             # "yes", "partly" or "no"
    evidence: str           # ISO date someone last looked or ran it
    risk: str = ""          # what is left uncovered, in one sentence
    owner: str = ""
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
    """What an answer is worth today. An old yes is only a partly."""
    if answer is None:
        return "no", "no answer"
    age = (today - date.fromisoformat(answer.evidence)).days
    if answer.status == "yes" and age > MAX_AGE:
        return "partly", f"evidence is {age} days old"
    return answer.status, ""


def review(questions, answers, today):
    """(verdict, reasons)."""
    stop, named = [], []
    for q in questions:
        a = answers.get(q.key)
        status, note = standing(a, today)
        if status == "yes":
            continue
        what = f"{q.key}: {status}" + (f", {note}" if note else "")
        if status == "no" or q.blocker:
            stop.append(what)
        elif a.risk and a.owner and a.days > 0:
            named.append(f"{what}; {a.risk}; {a.owner}, {a.days} days")
        else:
            stop.append(f"{what}; the risk has no name, owner or date")
    if stop:
        return "not yet", stop
    if named:
        return "launch with named risks", named
    return "launch", []
