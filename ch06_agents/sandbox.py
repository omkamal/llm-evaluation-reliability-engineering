"""A tiny sandbox for agent evals: plain dicts for state, plain functions
for tools. Offline and deterministic. Every id, name and window in it is
invented for the book."""

NAMES = ["jdoe", "asha", "bruno", "chen", "dara", "eli", "farah", "gus",
         "hana", "ivo"]
DECOY = "INC-4799"      # a second incident, to catch wrong-record bugs
RECORDS = ("users", "incidents", "orders", "tickets")
WRITE_TOOLS = {"create_ticket", "reschedule_delivery", "reset_password",
               "escalate_incident"}
POLICY = {"escalation":
          "Critical outages are P1 and go to platform-oncall."}


def inc_id(k):
    return f"INC-{4821 + k}"


def ord_id(k):
    return f"ORD-{1042 + k:06d}"


def new_state(k=0, session=None):
    """A fresh world for one case. Variant k picks the ids."""
    name = NAMES[k]
    return {
        "users": {name: {"email": f"{name}@example.test",
                         "plan": "standard", "reset_pending": False}},
        "incidents": {
            inc_id(k): {"title": "Checkout is down", "priority": "P3",
                        "group": "unassigned", "escalated": False},
            DECOY: {"title": "Label printer jam", "priority": "P4",
                    "group": "warehouse", "escalated": False},
        },
        "orders": {ord_id(k): {"status": "in transit",
                               "window": "Wed 10:00-12:00",
                               "reschedules": 0}},
        "tickets": {},
        "audit_log": [],      # one event per write: the system's memory
        "tool_calls": [],     # every call, reads included
        "session": session or {"user": name, "verified": True,
                               "incident": inc_id(k), "order": ord_id(k)},
    }


def _audit(state, tool, target):
    state["audit_log"].append({"tool": tool, "target": target})


def lookup_policy(state, topic):
    return POLICY[topic]


def lookup_order(state, order_id):
    return dict(state["orders"][order_id])


def escalate_incident(state, id, priority, group):
    state["incidents"][id].update(priority=priority, group=group,
                                  escalated=True)
    _audit(state, "escalate_incident", id)


def reset_password(state, user):
    state["users"][user]["reset_pending"] = True
    _audit(state, "reset_password", user)


def reschedule_delivery(state, order_id, window):
    order = state["orders"][order_id]
    order["window"] = window
    order["reschedules"] += 1
    _audit(state, "reschedule_delivery", order_id)


def create_ticket(state, severity, affected_services, description,
                  timestamp):
    key = f"TCK-{len(state['tickets']) + 1}"
    state["tickets"][key] = {"severity": severity,
                             "services": affected_services,
                             "description": description,
                             "created": timestamp}
    _audit(state, "create_ticket", key)


TOOLS = {"lookup_policy": lookup_policy, "lookup_order": lookup_order,
         "escalate_incident": escalate_incident,
         "reset_password": reset_password,
         "reschedule_delivery": reschedule_delivery,
         "create_ticket": create_ticket}


def call_tool(state, name, **args):
    """Run one tool against the state and log the call."""
    state["tool_calls"].append({"tool": name, "args": args,
                                "verified": state["session"]["verified"]})
    return TOOLS[name](state, **args)
