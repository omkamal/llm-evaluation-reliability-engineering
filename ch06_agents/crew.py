"""A four-stage Relay Crew, small enough to read: Planner, Researcher,
Summarizer, Actioner. It has the same shape as a single agent, so the
same harness grades the whole run; each handoff is also recorded so a
failure can be pinned on the hop that caused it."""
from ch06_agents.relays import HANDOFF, intent

NEEDS = {"action", "order", "window"}   # what the Actioner must receive
DEFAULT_WINDOW = "Mon 08:00-10:00"      # a quiet fallback hides the bug


def planner(message, session):
    window = message.split(" to ")[-1]
    return {"action": "reschedule", "order": session["order"],
            "window": window}


def researcher(packet, call):
    order = call("lookup_order", order_id=packet["order"])
    return dict(packet, status=order["status"])


def lossy_summarizer(packet):
    """Keeps the gist and drops a field: the failure to catch."""
    return {k: packet[k] for k in ("action", "order", "status")}


def careful_summarizer(packet):
    return {k: packet[k] for k in NEEDS | {"status"}}


def actioner(packet, call):
    window = packet.get("window", DEFAULT_WINDOW)
    call("reschedule_delivery", order_id=packet["order"], window=window)
    return f"Your delivery is now booked for {window}."


class Crew:
    """Callable like any agent. Keeps the packet seen after each stage."""

    def __init__(self, summarizer):
        self.summarizer, self.stages = summarizer, []

    def __call__(self, history, session, call):
        if intent(history[0]) != "reschedule":
            return HANDOFF
        self.stages = []
        packet = planner(history[0], session)
        self.stages.append(("planner", packet))
        packet = researcher(packet, call)
        self.stages.append(("researcher", packet))
        packet = self.summarizer(packet)
        self.stages.append(("summarizer", packet))
        return actioner(packet, call)


def lost_at(stages):
    """The first stage whose packet lacks something the Actioner needs."""
    for name, packet in stages:
        missing = NEEDS - packet.keys()
        if missing:
            return name, sorted(missing)
    return None
