"""Policy as code: the rules live here, versioned and tested, not in a
prompt that asks nicely. Changing the refund limit is a one-line,
reviewed change."""
from dataclasses import dataclass

from ch02_trust_outputs.refund import (AUTO_LIMIT_CENTS, DAY_LIMIT_CENTS,
                                       RefundArgs)
from ch02_trust_outputs.schema import Ticket
from ch17_security.schemas import (HandoffArgs, IncidentArgs, OrderArgs,
                                   PolicyArgs, RescheduleArgs, ResetArgs)


@dataclass(frozen=True)
class ToolRule:
    tier: int                  # 0 read-only, 1 low impact, 2 sensitive
    owned: str = ""            # argument that names a customer's record
    self_arg: str = ""         # argument that must be the caller's own id
    auto_cents: int = 0        # most the model may move unattended
    verified: bool = False     # needs a verified session
    day_cents: int = 0         # most per customer per day, all calls
    per_session: int = 0       # most calls per session (0: no count)
    args: type = None          # the strict schema; none means deny


# a tool that is not in this table does not exist for the model
RULES = {
    "lookup_order": ToolRule(0, owned="order_id", args=OrderArgs),
    "lookup_policy": ToolRule(0, args=PolicyArgs),
    "create_ticket": ToolRule(1, args=Ticket),
    "reschedule_delivery": ToolRule(1, owned="order_id",
                                    args=RescheduleArgs),
    "reset_password": ToolRule(1, self_arg="user", verified=True,
                               args=ResetArgs),
    "escalate_incident": ToolRule(2, per_session=1, args=IncidentArgs),
    "escalate_to_human": ToolRule(2, per_session=1, args=HandoffArgs),
    "issue_refund": ToolRule(2, owned="order_id", args=RefundArgs,
                             auto_cents=AUTO_LIMIT_CENTS,
                             day_cents=DAY_LIMIT_CENTS),
}


def describe(rule):
    """The rule in words, so the table in a review is generated from the
    same data the guard reads."""
    parts = ["auto"]
    if rule.auto_cents:
        parts[0] = f"auto to ${rule.auto_cents // 100}"
        if rule.day_cents:
            parts[0] += f" and ${rule.day_cents // 100} a day"
    if rule.per_session == 1:
        parts.append("once a session")
    elif rule.per_session:
        parts.append(f"{rule.per_session} a session")
    if rule.owned:
        parts.append("own orders only")
    if rule.self_arg:
        parts.append("own account only")
    if rule.verified:
        parts.append("verified session only")
    return ", ".join(parts)
