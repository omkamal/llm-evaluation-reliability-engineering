"""An audit trail that can be checked: one record per tool decision.

Chapter 6's sandbox kept {"tool", "target"}. A real record adds who,
which version, what was decided, who approved, and the trace id, and it
is chained so that editing an old record shows.
"""
import hashlib
import json
from collections import Counter

FIELDS = ("agent", "version", "tool", "args", "decision", "approver",
          "trace", "task")


class AuditLog:
    def __init__(self, clock):
        self.clock, self.events = clock, []

    def record(self, **fields):
        body = {k: fields.get(k) for k in FIELDS}
        body["target"] = (fields.get("args") or {}).get("order_id", "-")
        body["seq"], body["at"] = len(self.events), self.clock.now()
        body["prev"] = self.events[-1]["hash"] if self.events else "0" * 8
        text = json.dumps(body, sort_keys=True)
        body["hash"] = hashlib.sha256(text.encode()).hexdigest()[:8]
        self.events.append(body)
        return body

    def verify(self):
        """Index of the first record that was changed, or None."""
        prev = "0" * 8
        for i, event in enumerate(self.events):
            body = {k: v for k, v in event.items() if k != "hash"}
            text = json.dumps(body, sort_keys=True)
            good = hashlib.sha256(text.encode()).hexdigest()[:8]
            if event["prev"] != prev or event["hash"] != good:
                return i
            prev = event["hash"]
        return None

    def coverage(self, effects):
        """Share of changes seen in the world that have a record."""
        logged = Counter((e["tool"], e["target"]) for e in self.events
                         if e["decision"] == "allow")
        covered = 0
        for effect in effects:
            if logged[effect] > 0:
                logged[effect] -= 1
                covered += 1
        return covered / len(effects) if effects else 1.0
