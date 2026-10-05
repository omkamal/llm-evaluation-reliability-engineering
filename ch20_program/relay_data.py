"""Relay's invented roster, rota, pages, runbooks and answers.

Everything here is illustrative: it exists so that the checks in this
package have something to check. Dates are on or before 2026-10-05.
"""
from datetime import date, datetime

from ch20_program.findings import Finding
from ch20_program.owners import Item, Person
from ch20_program.pager import Page
from ch20_program.readiness import Answer
from ch20_program.runbooks import Runbook

TODAY = date(2026, 10, 5)

ROSTER = (
    Person("Sam", away=True, deputy="Priya"),
    Person("Priya", deputy="Sam"),
    Person("Marcus", deputy="Lena"),
    Person("Lena", deputy="Priya"),
    Person("Ines"),                       # joined three weeks ago
    Person("Jonas", left="2026-08-14"),   # built the policy index
)

# The sheet as it stood on Monday: one hero, one leaver, two orphans.
BEFORE = (
    Item("prompts and tool schemas", ("Sam",), ("Sam",)),
    Item("eval sets and the gate", ("Sam",), ("Priya",)),
    Item("policy index", ("Jonas",), ("Jonas",)),
    Item("tool contracts and tiers", ("Sam",), ("Lena",)),
    Item("SLO sheet and budget policy", ("Priya",), ("Marcus",)),
    Item("cost budgets", ("Sam",), ("Sam",)),
    Item("red-team set", ("Sam",), ("Lena",)),
    Item("credentials", ("Sam", "Priya"), ("Lena",)),
    Item("runbook and kill switch", ("Sam",), ("Priya", "Sam")),
    Item("postmortem actions", ("Sam",), ()),
)

AFTER = (
    Item("prompts and tool schemas", ("Sam", "Ines"), ("Sam",),
         ("Priya",), ("Marcus",)),
    Item("eval sets and the gate", ("Sam", "Marcus"), ("Priya",),
         ("Lena",), ("Ines",)),
    Item("policy index", ("Priya", "Ines"), ("Marcus",),
         ("Sam",), ("Lena",)),
    Item("tool contracts and tiers", ("Sam", "Lena"), ("Lena",),
         ("Priya",), ("Marcus",)),
    Item("SLO sheet and budget policy", ("Priya", "Sam"), ("Marcus",),
         ("Lena",), ("Ines",)),
    Item("cost budgets", ("Sam", "Priya"), ("Sam",),
         ("Marcus",), ("Lena",)),
    Item("red-team set", ("Ines", "Sam"), ("Lena",),
         ("Priya",), ("Marcus",)),
    Item("credentials", ("Priya", "Sam"), ("Lena",),
         ("Marcus",), ("Ines",)),
    Item("runbook and kill switch", ("Priya", "Ines"), ("Priya",),
         ("Sam",), ("Marcus",)),
    Item("postmortem actions", ("Sam", "Lena"), ("Priya",),
         ("Marcus",), ("Ines",)),
)

# Weekly rota from Monday 7 September: two people, so half the weeks each.
ROTA = ("Priya", "Sam")
ROTA_START = date(2026, 9, 7)
MONTH_DAYS = 28


def _page(day, hhmm, rule, acted=False):
    return Page(datetime.fromisoformat(f"{day}T{hhmm}"), rule, acted)


ONE_WINDOW = "good rate down, 1 window"
REFUND = "refund share up, 2 windows"

# Chapter 13's invented month on a calendar: 11 pages from the rule that
# cries wolf (2 acted on) and 2 from the refund rule (both acted on).
PAGES = (
    _page("2026-09-08", "23:20", ONE_WINDOW),
    _page("2026-09-12", "10:15", REFUND, True),
    _page("2026-09-15", "21:40", ONE_WINDOW),
    _page("2026-09-17", "02:05", ONE_WINDOW),
    _page("2026-09-19", "15:30", ONE_WINDOW, True),
    _page("2026-09-23", "21:05", ONE_WINDOW),
    _page("2026-09-23", "22:40", ONE_WINDOW),
    _page("2026-09-24", "01:10", ONE_WINDOW),
    _page("2026-09-24", "03:30", ONE_WINDOW),
    _page("2026-09-25", "16:45", ONE_WINDOW, True),
    _page("2026-09-30", "14:20", REFUND, True),
    _page("2026-10-02", "22:15", ONE_WINDOW),
    _page("2026-10-03", "04:10", ONE_WINDOW),
)

RUNBOOKS = (
    Runbook("provider failover", "Priya", 28, "2026-05-14", "Sam"),
    Runbook("kill switch and pin", "Priya", 24, "2026-09-22", "Sam"),
    Runbook("refund share", "Sam", 52, "2026-09-30", "Sam"),
)

# Each page alert and the runbook its message links to.
PAGE_ALERTS = {
    "BudgetBurnFast": "provider failover",
    "BudgetBurnMedium": "provider-failover-old",
    "CreditsOutsideBand": "kill switch and pin",
    "RefundShareUp": "refund share",
}

# The review on the eve of INC-6 (9 September), with what we know now.
EVE_OF_INC6 = {
    "gate": Answer("yes", "2026-09-04"),
    "slo": Answer("yes", "2026-08-28"),
    "trace": Answer("yes", "2026-08-28"),
    "cost": Answer("yes", "2026-09-01"),
    "failover": Answer("yes", "2026-05-14", "a provider loss may meet "
                       "an untested route", "Priya", 14),
    "guard": Answer("no", "2026-09-09"),
    "creds": Answer("no", "2026-09-09"),
    "review": Answer("no", "2026-09-09"),
    "kill": Answer("no", "2026-09-09"),
    "runbooks": Answer("partly", "2026-09-01", "no runbook for credits",
                       "Priya", 30),
    "data": Answer("yes", "2026-08-20"),
}

# The same review today.
NOW = {
    "gate": Answer("yes", "2026-10-02"),
    "slo": Answer("yes", "2026-10-04"),
    "trace": Answer("yes", "2026-09-28"),
    "cost": Answer("yes", "2026-10-04"),
    "failover": Answer("yes", "2026-05-14", "a provider loss may meet "
                       "an untested route", "Priya", 14),
    "guard": Answer("yes", "2026-09-17"),
    "creds": Answer("partly", "2026-10-02", "issue_refund credentials "
                    "are not yet scoped", "Lena", 14),
    "review": Answer("yes", "2026-09-28"),
    "kill": Answer("yes", "2026-09-22"),
    "runbooks": Answer("partly", "2026-10-05", "three page alerts reach "
                       "no sound runbook", "Priya", 14),
    "data": Answer("yes", "2026-10-05"),
}

# A team that bought tools first (invented).
TOOL_HEAVY = {"one log line per call", "traces"}
TOOL_HEAVY_BOUGHT = ("tracing platform", "eval platform", "gateway",
                     "guardrail library")

# Relay today: every control on levels 1 to 3, and three of the four on 4.
RELAY_HAS = {
    "validated output", "tool tiers and contracts", "idempotent writes",
    "one log line per call",
    "eval set from real failures", "intervals on scores",
    "calibrated judge", "state check on the riskiest tool",
    "SLO sheet and burn-rate pages", "bounded retries and budgets",
    "traces", "eval gate and staged releases",
    "one accountable owner per item", "kill switch and pin, drilled",
    "readiness review each quarter",
}

FINDINGS = (
    Finding("incident", "ownership check on every credit", "Sam",
            "2026-09-17", True, "G-OWN-01"),
    Finding("incident", "planted-note family into the suite", "Priya",
            "2026-09-15", True, "INJ-01 INJ-02 INJ-03"),
    Finding("incident", "kill switch and pin, drilled", "Priya",
            "2026-09-22", True, "D-KILL-01"),
    Finding("incident", "page on credits outside band", "Priya",
            "2026-09-24", True, "A-CRED-01"),
    Finding("incident", "scoped credentials for issue_refund", "Lena",
            "2026-10-02", False, "G-SCOPE-01"),
    Finding("near miss", "a tool-description edit nearly skipped the "
            "gate", "Sam", "2026-09-03", True, "gate path test"),
    Finding("near miss", "Provider B status mail went to a leaver",
            "Priya", "2026-09-18", True, "weekly ownership check"),
    Finding("game day", "failover held, the page linked a dead runbook",
            "Priya", "2026-05-28", False, ""),
)
