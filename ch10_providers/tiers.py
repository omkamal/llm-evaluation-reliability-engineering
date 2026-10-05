"""Service tiers: degrade on purpose, keep irreversible actions off."""
from dataclasses import dataclass

from ch10_providers.catalog import eligible, text_only

READ_ONLY = {"lookup_order", "lookup_policy"}
# changes the world or contacts someone: cannot be taken back
IRREVERSIBLE = {"issue_refund", "reschedule_delivery", "reset_password",
                "escalate_incident"}
FULL_BELT = READ_ONLY | IRREVERSIBLE | {"create_ticket",
                                        "escalate_to_human"}

# what the MODEL may call on each service tier (1 = full service)
MODEL_TOOLS = {1: FULL_BELT, 2: READ_ONLY, 3: set(), 4: set()}


class ActionBlocked(Exception):
    pass


def guard_tool(tool, tier, blocked_log):
    """Check a model's tool call against the tier it is running on."""
    if tool not in MODEL_TOOLS[tier]:
        blocked_log.append((tier, tool))
        raise ActionBlocked(f"{tool} is not allowed on tier {tier}")


def choose_tier(catalog, req, db_up=True):
    """1 full, 2 constrained, 3 cache or retrieval, 4 static guidance."""
    room = [p for p in catalog if p.free_slots > 0]
    if eligible(room, req):
        return 1
    if eligible(room, text_only(req)):
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
