"""A credential broker: short-lived tokens for one task and one tool.

The agents never hold a standing key. They ask the broker for a token
that names one tool, one customer and a money cap, and that expires.
"""
import itertools
from dataclasses import dataclass

from ch02_trust_outputs.refund import AUTO_LIMIT_CENTS

# The most each Crew agent can ever be granted (the belt of Chapter 2).
GRANTS = {
    "planner": {"escalate_to_human"},        # routes; no money tools
    "researcher": {"lookup_order", "lookup_policy"},     # reads only
    "summarizer": set(),                     # writes memory, no tools
    "actioner": {"create_ticket", "reschedule_delivery", "reset_password",
                 "escalate_incident", "issue_refund",
                 "escalate_to_human"},
}
CAPS_CENTS = {"issue_refund": AUTO_LIMIT_CENTS}   # above this: a person
TTL_SECONDS = 900          # fifteen minutes: one task, not one day


class NotGranted(Exception):
    """The role may never hold this tool, whatever it asks."""


class NeedsApproval(Exception):
    """The amount is over the cap and no person approved it."""


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Token:
    id: str
    agent: str
    task: str
    tool: str
    customer: str            # whose data this task may touch
    max_cents: int | None    # money cap, if the tool moves money
    expires_at: float
    approver: str | None = None


class Broker:
    def __init__(self, clock, grants=GRANTS, ttl=TTL_SECONDS):
        self.clock, self.grants, self.ttl = clock, grants, ttl
        self.live = {}                       # token id -> uses left
        self.numbers = itertools.count(1)

    def issue(self, agent, tool, task, customer, max_cents=None,
              approver=None, uses=1):
        if tool not in self.grants.get(agent, set()):
            raise NotGranted(f"{agent} may not hold {tool}")
        cap = CAPS_CENTS.get(tool)
        if cap is not None:
            max_cents = cap if max_cents is None else max_cents
            # only a person can lift the cap, and agents are not people
            if max_cents > cap and (approver is None
                                    or approver in self.grants):
                raise NeedsApproval(f"{max_cents} cents needs a person")
        token = Token(f"tok-{next(self.numbers):04d}", agent, task, tool,
                      customer, max_cents,
                      self.clock.now() + self.ttl, approver)
        self.live[token.id] = uses
        return token

    def check(self, token, tool, customer, amount_cents=0):
        """Raise Refused, with a code, unless this call is in scope."""
        if self.live.get(token.id, 0) < 1:
            raise Refused("unknown_or_used")
        if self.clock.now() >= token.expires_at:
            raise Refused("expired")
        if tool != token.tool:
            raise Refused("wrong_tool")
        if customer != token.customer:       # taken from the session
            raise Refused("wrong_customer")
        if token.max_cents is not None and amount_cents > token.max_cents:
            raise Refused("over_cap")

    def spend(self, token):
        self.live[token.id] -= 1
