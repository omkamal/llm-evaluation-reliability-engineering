"""An audit trail that can be checked: one record per tool decision.

Chapter 6's sandbox kept {"tool", "target"}. A real record adds who,
which version, what was decided, who approved, and the trace id. Each
record is sealed with an HMAC chained to the one before, by a sealer
whose key the log's writer never holds (in production, a key service).
"""
import hashlib
import hmac
import json
import secrets
from collections import Counter

FIELDS = ("agent", "version", "tool", "args", "decision", "approver",
          "trace", "task")


class Sealer:
    """Holds the key and the newest seal; whoever writes the log holds
    neither. It only appends, so it will not re-seal an old record."""

    def __init__(self, key=None):
        self._key = key or secrets.token_bytes(32)
        self.head = (0, "0" * 64)       # next seq, seal of the newest

    def _mac(self, body):
        text = json.dumps(body, sort_keys=True)
        return hmac.new(self._key, text.encode(),
                        hashlib.sha256).hexdigest()   # all 64 characters

    def seal(self, body):
        seq, prev = self.head
        body = dict(body, seq=seq, prev=prev)
        body["hash"] = self._mac(body)
        self.head = (seq + 1, body["hash"])
        return body

    def verify(self, events):
        """Index of the first record that was changed, moved or removed,
        or None. Records gone from the end are caught against the head."""
        prev = "0" * 64
        for i, event in enumerate(events):
            body = {k: v for k, v in event.items() if k != "hash"}
            good = hmac.compare_digest(str(event.get("hash")),
                                       self._mac(body))
            if (not good or event.get("seq") != i
                    or event.get("prev") != prev):
                return i
            prev = event["hash"]
        if (len(events), prev) != self.head:
            return len(events)          # the newest records are missing
        return None


class AuditLog:
    def __init__(self, clock, sealer=None):
        self.clock, self.events = clock, []
        self.sealer = sealer or Sealer()

    def record(self, **fields):
        body = {k: fields.get(k) for k in FIELDS}
        body["target"] = (fields.get("args") or {}).get("order_id", "-")
        body["at"] = self.clock.now()
        event = self.sealer.seal(body)
        self.events.append(event)
        return event

    def verify(self):
        """Index of the first record that was changed or is missing, or
        None. Only the sealer can check, because only it has the key."""
        return self.sealer.verify(self.events)

    def coverage(self, effects):
        """Share of changes seen in the world that have a record of the
        same tool, the same order and the same amount."""
        logged = Counter((e["tool"], e["target"],
                          (e["args"] or {}).get("amount_cents"))
                         for e in self.events if e["decision"] == "allow")
        covered = 0
        for effect in effects:
            if logged[effect] > 0:
                logged[effect] -= 1
                covered += 1
        return covered / len(effects) if effects else 1.0
