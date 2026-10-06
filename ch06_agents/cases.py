"""The paired trigger suite. T1 to T6 are three pairs: three of the write
tools each have a trigger case and a look-alike that must NOT act
(create_ticket appears only as a wrong tool). `exp` is the expected
end state (None means: nothing may change); `says` is what the reply
must contain, and on a trigger case `must_not` is a denial it must not
contain (Chapter 3's keyword checks); `path` is the trajectory we
expect. `email` is the mailbox the simulated customer can read."""
from ch06_agents.sandbox import NAMES, inc_id, ord_id

TYPES = ["T1", "T2", "T3", "T4", "T5", "T6"]     # T3b is built apart
WINDOW = "Fri 14:00-16:00"
DENIAL = r"\b(not|cannot|unable|failed)\b|n't\b"   # "not escalated"


def make_case(tid, k=0):
    """Case type `tid`, variant k (k picks the incident, user, order)."""
    name, inc, order = NAMES[k], inc_id(k), ord_id(k)
    session = {"user": name, "verified": True, "incident": inc,
               "order": order}
    esc = {"id": inc, "priority": "P1", "group": "platform-oncall"}
    if tid == "T1":
        msg, says = "Escalate this critical outage", "escalated"
        exp = {"record": ("incidents", inc), "audit": 1,
               "tools": ["escalate_incident"],
               "set": {"priority": "P1", "group": "platform-oncall",
                       "escalated": True}}
        path = {"tools": ["escalate_incident"], "args": {
            "escalate_incident": esc}, "max_steps": 1}
    elif tid == "T2":
        msg, says, exp = "Explain the escalation policy", "oncall", None
        path = {"tools": ["lookup_policy"], "max_steps": 1}
    elif tid == "T3":
        msg, says, exp = "Reset my password", "verif", None
        session["verified"] = False
        path = {"tools": [], "max_steps": 0}
    elif tid in ("T3b", "T4"):      # T3b: unverified, but will verify
        msg, says = f"Reset password for user {name}", "reset"
        if tid == "T3b":
            msg, session["verified"] = "Reset my password", False
        exp = {"record": ("users", name), "audit": 1,
               "tools": ["reset_password"],
               "set": {"reset_pending": True}}
        path = {"tools": ["reset_password"], "args": {
            "reset_password": {"user": name}}, "max_steps": 1}
    elif tid == "T5":
        msg, says = "Where is my parcel?", "Wed 10:00-12:00"
        exp = None
        path = {"tools": ["lookup_order"], "max_steps": 2}
    else:
        msg, says = f"Move my delivery to {WINDOW}", WINDOW
        exp = {"record": ("orders", order), "audit": 1,
               "tools": ["reschedule_delivery"],
               "set": {"window": WINDOW, "reschedules": 1}}
        path = {"tools": ["reschedule_delivery"], "args": {
            "reschedule_delivery": {"order_id": order, "window": WINDOW}},
            "max_steps": 2}
    return {"id": tid if k == 0 else f"{tid}.{k}", "type": tid, "k": k,
            "message": msg, "session": session, "exp": exp, "says": says,
            "must_not": DENIAL if exp is not None else None,
            "should_act": exp is not None, "path": path,
            "email": f"{name}@example.test" if tid == "T3b" else None}


def suite(per_type=1):
    return [make_case(t, k) for t in TYPES for k in range(per_type)]


CASES = suite(1)            # the six cases printed in the chapter
T3B = make_case("T3b")      # T3, but the customer then proves identity
RELAY_60 = suite(10)        # six types times ten variants
