"""Service tiers: degrade on purpose; below tier 1 the model never writes."""
from dataclasses import dataclass

from ch10_providers.catalog import available, text_only

READ_ONLY = {"lookup_order", "lookup_policy"}
# writes that can be fixed later (Chapter 0's tier 1)
FIXABLE = {"create_ticket", "reschedule_delivery", "reset_password"}
# moves money or pages someone: cannot be taken back
IRREVERSIBLE = {"issue_refund", "escalate_incident"}
FULL_BELT = READ_ONLY | FIXABLE | IRREVERSIBLE | {"escalate_to_human"}

# what the MODEL may call on each service tier (1 = full service):
# below tier 1 it writes nothing, fixable or not
MODEL_TOOLS = {1: FULL_BELT, 2: READ_ONLY, 3: set(), 4: set()}


class ActionBlocked(Exception):
    pass


def guard_tool(tool, tier, blocked_log):
    """Check a model's tool call against the tier it is running on."""
    if tool not in MODEL_TOOLS[tier]:
        blocked_log.append((tier, tool))
        raise ActionBlocked(f"{tool} is not allowed on tier {tier}")


def choose_tier(catalog, req, db_up=True, tripped=()):
    """1 full, 2 constrained, 3 cache or retrieval, 4 static guidance."""
    if available(catalog, req, tripped):      # the router's own test
        return 1
    if available(catalog, text_only(req), tripped):
        return 2                 # residency still applies on every tier
    return 3 if db_up else 4


@dataclass(frozen=True)
class Notice:
    what: str      # what is happening, in plain words
    works: str     # what still works
    next: str      # what the customer can do or expect

    def text(self):
        return f"{self.what} {self.works} {self.next}"


def support_open(hour):
    return 8 <= hour < 20          # human agents, 8:00 to 20:00


def notice(tier, hour):
    """The honest, short message for a degraded tier."""
    person = ("A person can pick this up now." if support_open(hour)
              else "A person will reply from 8:00 tomorrow.")
    return {
        2: Notice("I am running in a reduced mode, so answers are short.",
                  "I can still look up orders and policies.",
                  "I cannot change orders now; I can pass it on."),
        3: Notice("I am answering from saved information right now.",
                  "Order status and our policies are available.",
                  f"For anything else I will open a ticket. {person}"),
        4: Notice("I cannot answer right now.",
                  "Our help page has the basics.",
                  f"I have saved your message. {person}"),
    }[tier]
