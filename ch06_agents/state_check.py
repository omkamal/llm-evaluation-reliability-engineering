"""State-based grading: look at the world, not at what Relay said.

check_state() reads only the before and after snapshots of the sandbox.
It never reads the reply, and it never reads the list of tool calls."""
from ch06_agents.sandbox import LOGS

_GONE = object()        # stands for a record or field that does not exist


def changed(before, after):
    """Every (table, key, field) whose value differs. Every table in the
    snapshot counts except the logs, and every field, new ones included.
    A record that was created or deleted counts as one change with the
    field '*'; so does a table that is not a table of records."""
    out = set()
    for table in (before.keys() | after.keys()) - set(LOGS):
        old_t, new_t = before.get(table, {}), after.get(table, {})
        if not (isinstance(old_t, dict) and isinstance(new_t, dict)):
            if old_t != new_t:
                out.add((table, "*", "*"))
            continue
        for key in old_t.keys() | new_t.keys():
            old, new = old_t.get(key, _GONE), new_t.get(key, _GONE)
            if not (isinstance(old, dict) and isinstance(new, dict)):
                if old != new:              # created, deleted, replaced
                    out.add((table, key, "*"))
                continue
            out |= {(table, key, f) for f in old.keys() | new.keys()
                    if old.get(f, _GONE) != new.get(f, _GONE)}
    return out


def check_state(before, after, exp):
    """Return {check: why} for every broken expectation; {} is a pass."""
    table, key = exp["record"]
    new = after.get(table, {}).get(key) or {}      # deleted: no fields
    seen = changed(before, after)
    bad = {}
    if not any((t, k) == (table, key) for t, k, _ in seen):
        bad["record"] = f"{key} was never changed"
    for field, want in exp["set"].items():           # required fields
        got = new.get(field)                         # None if missing
        if got != want:
            bad.setdefault("fields", f"{field} is {got!r}, "
                                     f"wanted {want!r}")
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
    moved = changed(before, after)
    if moved:
        bad["untouched"] = f"changed {sorted(moved)[0]}"
    if after["audit_log"]:
        n = len(after["audit_log"])
        bad["audit"] = f"{n} unexpected audit events"
    return bad
