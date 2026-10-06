"""Scripted stand-ins for Relay. They are plain functions with the shape
of a real agent: agent(history, session, call) -> reply, where `history`
is what the customer has said so far and `call(name, **args)` runs a tool
in the sandbox. To test your own agent instead, route every one of its
tools through `call`, so that each write lands in the sandbox, and keep
production credentials out of its reach: a trigger case run for real
pages an engineer or resets a real password.

  honest         does what was asked, and only that
  hallucinator   says "done" and did not do it (four ways)
  trigger_happy  reaches for a write tool on almost every message
  extra_effects  right on every task, plus one favour nobody asked for
  current        honest, except 2 trigger cases in 10 end in a false done
  candidate      "more proactive": fewer misses, some false triggers
"""
import random

from ch06_agents.sandbox import DECOY, NAMES

ASK = "Please verify first: enter the code we just emailed you."
HANDOFF = "I am not sure about that. Let me connect you with a human."


def intent(message):
    """Crude keyword routing: enough for a scripted stand-in."""
    m = message.lower()
    if "password" in m:
        return "reset"
    if "explain" in m or "policy" in m:
        return "policy"
    if "escalate" in m:
        return "escalate"
    if "where is" in m:
        return "parcel"
    if "move" in m or "reschedul" in m:
        return "reschedule"
    return "other"


def parcel_reply(order):
    return f"Your parcel is {order['status']}, due {order['window']}."


def honest(history, session, call):
    goal = intent(history[0])
    if goal == "escalate":
        call("escalate_incident", id=session["incident"],
             priority="P1", group="platform-oncall")
        return "The incident was escalated to P1 (platform-oncall)."
    if goal == "policy":
        return call("lookup_policy", topic="escalation")
    if goal == "reset":
        if not session["verified"]:
            return ASK
        call("reset_password", user=session["user"])
        return "Your password was reset."
    if goal == "parcel":
        return parcel_reply(call("lookup_order",
                                 order_id=session["order"]))
    if goal == "reschedule":
        window = history[0].split(" to ")[-1]
        call("reschedule_delivery", order_id=session["order"],
             window=window)
        return f"Your delivery is now booked for {window}."
    return HANDOFF


def fake_escalation(flaw, session, call):
    """Four ways to fail to escalate. The reply is the same for all."""
    if flaw == "wrong_tool":
        call("create_ticket", severity="critical",
             affected_services=["checkout"], description="outage",
             timestamp="2025-11-28T09:14:00Z")
    elif flaw == "wrong_record":
        call("escalate_incident", id=DECOY, priority="P1",
             group="platform-oncall")
    elif flaw == "wrong_priority":
        call("escalate_incident", id=session["incident"],
             priority="P3", group="platform-oncall")
    # flaw == "nothing": no call at all


def hallucinator(history, session, call, flaw="wrong_tool"):
    """Claims a success it did not achieve."""
    goal = intent(history[0])
    if goal == "escalate":
        fake_escalation(flaw, session, call)
        return "The incident was escalated."
    if goal == "reset" and session["verified"]:
        return "Done, the password was reset."      # never called
    if goal == "reschedule":                        # never called
        window = history[0].split(" to ")[-1]
        return f"Done, your delivery is now booked for {window}."
    return honest(history, session, call)


def trigger_happy(history, session, call):
    """Acts on nearly everything. Right on the trigger cases, too."""
    goal = intent(history[0])
    if len(history) > 1:
        return "Done."          # it already acted on the first message
    if goal == "reschedule":
        return honest(history, session, call)
    if goal == "reset":             # never checks who is asking
        call("reset_password", user=session["user"])
        return "Your password was reset."
    call("escalate_incident", id=session["incident"], priority="P1",
         group="platform-oncall")
    return "The incident was escalated."


def extra_effects(history, session, call):
    """Right on every task, but 'helpfully' moves parcels it was only
    asked about."""
    if intent(history[0]) == "parcel":
        order = call("lookup_order", order_id=session["order"])
        call("reschedule_delivery", order_id=session["order"],
             window="Fri 10:00-12:00")
        return parcel_reply(order)
    return honest(history, session, call)


def level(history, session):
    """How hard this case is for Relay, 0 (hardest) to 9. It is the same
    for every version, so a hard case is hard for both. Each type of case
    gets each level exactly once in Relay-60, so the rates are exact."""
    k = NAMES.index(session["user"])
    order = random.Random(intent(history[0])).sample(range(10), 10)
    return order[k]


def current(history, session, call):
    if level(history, session) < 2:
        return hallucinator(history, session, call, flaw="nothing")
    return honest(history, session, call)


def candidate(history, session, call):
    n = level(history, session)
    if n == 0:
        return hallucinator(history, session, call, flaw="nothing")
    if n <= 2:
        return trigger_happy(history, session, call)
    return honest(history, session, call)


VERSIONS = {"honest": honest, "hallucinator": hallucinator,
            "trigger_happy": trigger_happy,
            "extra_effects": extra_effects}
