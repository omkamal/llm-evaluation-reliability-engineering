"""An error-aware repair loop, capped, ending in a typed failure and never a guess."""
import json
from dataclasses import dataclass

from pydantic import ValidationError

from ch02_trust_outputs.schema import Ticket

MAX_ATTEMPTS = 3


@dataclass
class Reply:
    text: str
    finish_reason: str = "stop"   # or "length" (cut off), or "refusal"


@dataclass
class Failure:
    reason: str        # "refused", "truncated", "invalid_after_repair"
    errors: list


def repair_prompt(bad_output, schema, errors):
    """Show the model its answer, the rules, and the specific errors."""
    lines = "\n".join(f"- {loc}: {msg}" for loc, msg in errors)
    return (f"Your answer:\n{bad_output}\n\nSchema:\n{json.dumps(schema)}\n\n"
            f"It failed validation:\n{lines}\nReturn corrected JSON only.")


def get_ticket(prompt, call_llm):
    reply = call_llm(prompt)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if reply.finish_reason == "refusal":
            return Failure("refused", [])       # not a format problem
        try:
            return Ticket.model_validate_json(reply.text)
        except ValidationError as e:
            errors = [(".".join(map(str, x["loc"])), x["msg"])
                      for x in e.errors()]
        if reply.finish_reason == "length":
            return Failure("truncated", errors)     # repair cannot help
        if attempt < MAX_ATTEMPTS:
            schema = Ticket.model_json_schema()
            reply = call_llm(repair_prompt(reply.text, schema, errors))
    return Failure("invalid_after_repair", errors)
