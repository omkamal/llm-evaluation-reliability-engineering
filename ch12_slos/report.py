"""A one-page SLO report for people who do not read dashboards."""
from dataclasses import dataclass

from ch12_slos.budget import policy_rung


@dataclass(frozen=True)
class Spend:
    chats: int              # failed chats this item used up
    planned: bool           # spent on purpose, or not
    what: str


def render_report(period, results, allowed, spends, notes):
    """Plain-language text. `results` comes from sheet.check_sheet."""
    kept = sum(ok for _, _, ok in results)
    lines = [f"Relay service report, {period}", ""]
    lines.append(f"Promises kept: {kept} of {len(results)}")
    for slo, value, ok in results:
        if not ok:
            lines.append("  Missed: " + notes[slo.name])
    used = sum(s.chats for s in spends)
    left = (allowed - used) / allowed
    lines += ["", f"Failed chats we agreed we could afford: {allowed:,}",
              f"  Used {used:,} ({1 - left:.0%}), left {allowed - used:,}"
              f" ({left:.0%})"]
    for s in spends:
        kind = "on purpose" if s.planned else "not planned"
        lines.append(f"  {s.chats:>5,} {kind}: {s.what}")
    lines += ["", f"Error-budget policy for chats: {policy_rung(left)}."]
    return lines
