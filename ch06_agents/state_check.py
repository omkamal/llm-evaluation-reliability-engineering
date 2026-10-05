"""State-based grading: look at the world, not at what Relay said.

check_state() reads only the before and after snapshots of the sandbox.
It never reads the reply, and it never reads the list of tool calls."""
from ch06_agents.sandbox import RECORDS


def changed(before, after):
    """Every (table, key, field) whose value differs. A record that was
    created or deleted counts as one change with the field '*'."""
    out = set()
    for table in RECORDS:
        for key in before[table].keys() | after[table].keys():
            old, new = before[table].get(key), after[table].get(key)
            if old is None or new is None:
                out.add((table, key, "*"))
            else:
                out |= {(table, key, f) for f in old if old[f] != new[f]}
    return out


def check_state(before, after, exp):
    """Return {check: why} for every broken expectation; {} is a pass."""
    table, key = exp["record"]
    new = after[table][key]
    seen = changed(before, after)
    bad = {}
    if not any((t, k) == (table, key) for t, k, _ in seen):
        bad["record"] = f"{key} was never changed"
    for field, want in exp["set"].items():           # required fields
        if new[field] != want:
            bad.setdefault(
                "fields", f"{field} is {new[field]!r}, wanted {want!r}")
    wanted = {(table, key, f) for f in exp["set"]}
    if seen - wanted:                                # nothing else moved
        bad["untouched"] = f"also changed {sorted(seen - wanted)[0]}"
    events = [e for e in after["audit_log"] if e["target"] == key]
    if len(events) != exp["audit"]:                  # exactly once
        bad["audit"] = (f"{len(events)} audit events, "
                        f"wanted {exp['audit']}")
    used = [e["tool"] for e in after["audit_log"]]
    if used != exp["tools"]:                         # right tool only
        bad["tool"] = f"wrote with {used}, wanted {exp['tools']}"
    return bad


def check_untouched(before, after):
    """For a non-trigger case: the world must not have moved at all."""
    bad = {}
    if changed(before, after):
        bad["untouched"] = f"changed {sorted(changed(before, after))[0]}"
    if after["audit_log"]:
        n = len(after["audit_log"])
        bad["audit"] = f"{n} unexpected audit events"
    return bad
