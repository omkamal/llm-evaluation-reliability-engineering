"""The cost-per-resolved-task dashboard, as a spec you can check."""
from dataclasses import dataclass

from ch12_slos.sheet import SHEET

TARGET = next(s.target for s in SHEET
              if s.name == "cost per resolved task")


@dataclass(frozen=True)
class Panel:
    metric: str
    cut_by: tuple
    alert: str          # "page", "ticket" or "dashboard" (Chapter 13)
    owner: str
    pairs_with: str = ""    # a cost panel must name its quality panel


PANELS = (
    Panel("cost per resolved task, 7 d", ("feature", "tenant", "tier"),
          "ticket", "Sam", pairs_with="judge pass rate"),
    Panel("judge pass rate, with interval", ("feature", "tier"),
          "ticket", "Priya"),
    Panel("tokens per task, p50 and p95", ("feature", "turns"),
          "dashboard", "Sam"),
    Panel("tier mix and cascade step-up rate", ("feature",),
          "ticket", "Sam", pairs_with="judge pass rate"),
    Panel("prompt-cache hit rate", ("feature",), "dashboard", "Priya"),
    Panel("semantic-cache hit and false-hit rate", ("tenant",),
          "ticket", "Priya", pairs_with="judge pass rate"),
    Panel("semantic-cache hits across tenants (must be 0)", ("tenant",),
          "page", "Lena"),
    Panel("spend against monthly cost budget", ("team",),
          "ticket", "Sam"),
    Panel("calls in flight against the limit, at peak", ("provider",),
          "page", "Sam"),
)


def check_spec(panels=PANELS):
    """Problems that would make the dashboard mislead you."""
    problems = []
    for p in panels:
        if not (p.owner and p.alert and p.cut_by):
            problems.append(f"{p.metric}: needs an owner, alert and cut")
        if p.alert not in {"page", "ticket", "dashboard"}:
            problems.append(f"{p.metric}: unknown route {p.alert!r}")
    names = [p.metric for p in panels]
    for p in panels:
        if p.pairs_with and not any(n.startswith(p.pairs_with)
                                    for n in names):
            problems.append(f"{p.metric}: no panel for {p.pairs_with}")
    return problems
