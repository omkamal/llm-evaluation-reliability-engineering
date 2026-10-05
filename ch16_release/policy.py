"""The error-budget policy, enforced inside the release process.

Chapter 12 wrote the ladder; here a release asks the ladder before it
ships. A change is anything that can alter behaviour: a prompt, a model
alias, a tool schema, an index, a threshold. Chapter 15's gate decides
whether a change is good; this check decides whether now is the time.
"""
from dataclasses import dataclass

from ch12_slos.budget import policy_rung

RISKY = {"model", "prompt", "tool_schema", "index", "threshold"}
FIXES = {"reliability_fix", "security_fix"}


@dataclass(frozen=True)
class Change:
    kind: str            # one of RISKY, FIXES, or a routine kind
    summary: str

    @property
    def risky(self):
        return self.kind in RISKY


def release_check(change, left, risky_in_flight=0):
    """(decision, reason) for one change, given the budget left (0 to 1)."""
    rung = policy_rung(left)
    if change.kind in FIXES:
        return "ship", "a fix: allowed on every rung"
    if rung == "ship features":
        return "ship", f"{left:.0%} of the error budget left"
    if rung == "ship, one risky change at a time":
        if change.risky and risky_in_flight:
            return "hold", "another risky change is already in flight"
        return "ship", f"{left:.0%} left, nothing else risky in flight"
    if rung == "reliability fixes only":
        return "hold", f"{left:.0%} left: reliability fixes only"
    if change.risky:
        return "hold", "error budget spent: risky releases frozen"
    return "ship", "error budget spent, but this change is routine"
