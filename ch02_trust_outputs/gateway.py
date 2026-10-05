"""The validation gateway: every model output is checked at one door, before anything else sees it."""
import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from ch02_trust_outputs.schema import Ticket


@dataclass
class Quarantined:
    raw: str
    errors: list                 # [(location, error type, message), ...]
    prompt_version: str
    model_version: str


@dataclass
class Gateway:
    schema: type = Ticket
    # approved severity mappings only
    aliases: dict = field(default_factory=dict)
    accepted: int = 0
    aliased: int = 0
    quarantine: list = field(default_factory=list)

    def check(self, raw, *, prompt_version, model_version):
        """Return a validated object, or None after quarantining."""
        try:
            if self.aliases:
                data = json.loads(raw)
                mapped = self.aliases.get(data.get("severity"))
                if mapped:   # explicit, approved, counted
                    data["severity"] = mapped
                    self.aliased += 1
                obj = self.schema.model_validate(data)
            else:
                obj = self.schema.model_validate_json(raw)
        except ValidationError as exc:
            errors = [(".".join(map(str, e["loc"])), e["type"], e["msg"])
                      for e in exc.errors()]
        except json.JSONDecodeError as exc:
            errors = [("", "json_invalid", exc.msg)]
        else:
            self.accepted += 1
            return obj
        self.quarantine.append(
            Quarantined(raw, errors, prompt_version, model_version))
        return None

    @property
    def quarantine_rate(self):
        total = self.accepted + len(self.quarantine)
        return len(self.quarantine) / total if total else 0.0
