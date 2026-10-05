"""Relay's SLO sheet: two layers, one 28-day clock."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SLO:
    layer: str              # "chat" (call and chat) or "task"
    name: str
    target: float
    at_least: bool          # True: at least the target; False: under it
    unit: str               # "%", "s" or "$"
    window_days: int

    def met(self, value):
        if self.at_least:
            return value >= self.target
        return value < self.target

    def margin(self, value):
        gap = value - self.target
        return gap if self.at_least else -gap


SHEET = (
    SLO("chat", "availability", 99.5, True, "%", 28),
    SLO("chat", "first token within 2 s", 95.0, True, "%", 28),
    SLO("chat", "first-pass validity", 98.0, True, "%", 28),
    SLO("chat", "answers judged good", 90.0, True, "%", 7),
    SLO("chat", "refusals", 2.0, False, "%", 7),
    SLO("chat", "cost per success", 0.04, False, "$", 7),
    SLO("task", "task success", 99.0, True, "%", 28),
    SLO("task", "p95 task latency", 8.0, False, "s", 28),
    SLO("task", "judge pass, weekly", 90.0, True, "%", 7),
    SLO("task", "cost per resolved task", 0.06, False, "$", 7),
)


def check_sheet(measured, sheet=SHEET):
    """[(slo, value, met)] for every SLO that has a measurement."""
    return [(s, measured[s.name], s.met(measured[s.name]))
            for s in sheet if s.name in measured]


def show(slo, value):
    """A value or target with its unit: 99.5%, 8 s, $0.04."""
    if slo.unit == "$":
        return f"${value:g}"
    return f"{value:g}{'' if slo.unit == '%' else ' '}{slo.unit}"


def line(slo, value, ok):
    sign = ">=" if slo.at_least else "<"
    verdict = "met" if ok else "MISSED"
    return (f"{slo.layer:<5}{slo.name:<24}{show(slo, value):>8}  "
            f"{sign} {show(slo, slo.target):<7}{verdict}")
