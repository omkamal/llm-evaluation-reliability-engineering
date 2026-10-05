"""Policy as code: the rules live here, versioned and tested, not in a
prompt that asks nicely. Changing the refund limit is a one-line,
reviewed change."""
from dataclasses import dataclass

from ch02_trust_outputs.refund import AUTO_LIMIT_CENTS


@dataclass(frozen=True)
class ToolRule:
    tier: int                  # 0 read-only, 1 low impact, 2 sensitive
    owned: str = ""            # argument that names a customer's record
    self_arg: str = ""         # argument that must be the caller's own id
    auto_cents: int = 0        # most the model may move unattended
    verified: bool = False     # needs a verified session


# a tool that is not in this table does not exist for the model
RULES = {
    "lookup_order": ToolRule(0, owned="order_id"),
    "lookup_policy": ToolRule(0),
    "create_ticket": ToolRule(1),
    "reschedule_delivery": ToolRule(1, owned="order_id"),
    "reset_password": ToolRule(1, self_arg="user", verified=True),
    "escalate_incident": ToolRule(2),
    "escalate_to_human": ToolRule(2),
    "issue_refund": ToolRule(2, owned="order_id",
                             auto_cents=AUTO_LIMIT_CENTS),
}


def describe(rule):
    """The rule in words, so the table in a review is generated from the
    same data the guard reads."""
    parts = ["auto"]
    if rule.auto_cents:
        parts[0] = f"auto to ${rule.auto_cents // 100}, then a person"
    if rule.owned:
        parts.append("own orders only")
    if rule.self_arg:
        parts.append("own account only")
    if rule.verified:
        parts.append("verified session only")
    return ", ".join(parts)
