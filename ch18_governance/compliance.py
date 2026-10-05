"""A control map and a retention check. Not legal advice.

A control with no owner, no evidence or no criterion is a wish, so the
map is data and a function lists the wishes.
"""
from dataclasses import dataclass

from ch07_datasets.redact import redact


@dataclass(frozen=True)
class Control:
    name: str
    chapter: int
    soc2: tuple          # criteria it can supply evidence for
    nist: tuple          # AI RMF subcategories it supports
    evidence: str        # what you would hand an auditor
    owner: str


CONTROLS = [
    Control("scoped, short-lived credentials", 18,
            ("CC6.1", "CC6.2", "CC6.3"), ("GOVERN 3.2",),
            "grants file in git, broker issue log", "platform"),
    Control("audit trail with a trace id", 18,
            ("CC7.2", "CC7.3"), ("MANAGE 4.1",),
            "chain check, share of actions with a record", "platform"),
    Control("inventory and change control", 18,
            ("CC8.1", "CC3.2"), ("GOVERN 1.6",),
            "inventory audit, change records with approver", "release"),
    Control("human review of high-value actions", 18,
            ("CC6.3", "PI1.3"), ("MAP 3.5", "GOVERN 3.2"),
            "review policy, queue and override numbers", "support ops"),
    Control("validation gateway and tool checks", 2,
            ("PI1.2", "PI1.4"), ("MEASURE 2.5",),
            "quarantine log, rejections per layer", "backend"),
    Control("traces, SLOs and drift alarms", 12,
            ("CC4.1", "CC7.2"), ("MEASURE 3.1", "MANAGE 4.1"),
            "SLO sheet, alert log with precision", "reliability"),
    Control("provider terms and residency routing", 10,
            ("CC9.2", "P6.4"), ("MANAGE 3.1",),
            "terms file per provider, residency violations", "platform"),
    Control("retention schedule and redaction", 11,
            ("P4.2", "P4.3", "C1.2"), ("MEASURE 2.10",),
            "retention audit, personal data found in stores", "data"),
]


def gaps(controls):
    """The wishes: controls missing an owner, evidence or criteria."""
    out = []
    for c in controls:
        for field in ("owner", "evidence", "soc2", "nist"):
            if not getattr(c, field):
                out.append(f"{c.name}: no {field}")
    return out


def criteria_evidenced(controls):
    return sorted({k for c in controls for k in c.soc2})


def retention_findings(stores, policy_days):
    """Stores that keep data longer than the written policy allows."""
    return [f"{s['name']}: oldest {s['oldest_days']} days, "
            f"policy {policy_days[s['name']]}"
            for s in stores if s["oldest_days"] > policy_days[s["name"]]]


def personal_data_found(records):
    """Count what Chapter 7's redactor still finds in stored text.
    Order ids stay in traces by design, so they are not counted."""
    total = 0
    for text in records:
        _, counts = redact(text)
        total += sum(n for kind, n in counts.items() if kind != "ORDER")
    return total
