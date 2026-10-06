"""A four-stage Relay Crew, small enough to read: Planner, Researcher,
Summarizer, Actioner. It has the same shape as a single agent, so the
same harness grades the whole run. Each part is graded too: every
handoff is recorded, so a failure can be pinned on the hop that caused
it, and every tool call is tagged with the stage that made it, so we can
check that only the Actioner writes."""
from ch06_agents.relays import HANDOFF, intent
from ch06_agents.sandbox import WRITE_TOOLS

NEEDS = {"action", "order", "window"}   # what the Actioner must receive
DEFAULT_WINDOW = "Mon 08:00-10:00"      # a quiet fallback hides the bug


def planner(message, session):
    window = message.split(" to ")[-1]
    return {"action": "reschedule", "order": session["order"],
            "window": window}


def researcher(packet, call):
    order = call("lookup_order", order_id=packet["order"])
    return dict(packet, status=order["status"])


def eager_researcher(packet, call):
    """Reschedules at once: a write by a stage that should only read."""
    call("reschedule_delivery", order_id=packet["order"],
         window=packet["window"])
    return researcher(packet, call)


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
    """Callable like any agent. Keeps the packet seen after each stage,
    and (stage, tool) for every call."""

    def __init__(self, summarizer, researcher=researcher):
        self.summarizer, self.researcher = summarizer, researcher
        self.stages, self.calls = [], []

    def as_stage(self, name, call):
        """The `call` a stage gets: it records who made each call."""
        def tagged(tool, **args):
            self.calls.append((name, tool))
            return call(tool, **args)
        return tagged

    def __call__(self, history, session, call):
        if intent(history[0]) != "reschedule":
            return HANDOFF
        self.stages, self.calls = [], []
        packet = planner(history[0], session)
        self.stages.append(("planner", packet))
        research = self.as_stage("researcher", call)
        packet = self.researcher(packet, research)
        self.stages.append(("researcher", packet))
        packet = self.summarizer(packet)
        self.stages.append(("summarizer", packet))
        return actioner(packet, self.as_stage("actioner", call))


def lost_at(stages):
    """The first stage whose packet lacks something the Actioner needs."""
    for name, packet in stages:
        missing = NEEDS - packet.keys()
        if missing:
            return name, sorted(missing)
    return None


def wrong_writers(calls):
    """Stages other than the Actioner that used a write tool."""
    return sorted({stage for stage, tool in calls
                   if tool in WRITE_TOOLS and stage != "actioner"})
