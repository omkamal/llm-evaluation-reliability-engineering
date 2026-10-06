"""Relay's ticket schema: one definition, three jobs (prompt, provider schema, validator)."""
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field

SEVERITIES = ("low", "medium", "high", "critical")

Text = Annotated[str, Field(pattern=r"\S")]  # min_length=1 passes " "


# strict: nothing is converted, so 0 never becomes a date in 1970
class Ticket(BaseModel, extra="forbid", strict=True):
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="critical: checkout or login is down for everyone")
    affected_services: list[Text] = Field(min_length=1)
    description: Text
    timestamp: AwareDatetime = Field(
        description="ISO 8601 UTC, for example 2025-11-28T09:14:00Z")


# The Black Friday reply: perfectly valid JSON, and wrong in two ways.
BLACK_FRIDAY = (
    '{"severity": "urgent", "affected_services": [], '
    '"description": "Checkout is down for all customers", '
    '"timestamp": "2025-11-28T09:14:00Z"}'
)
GOOD_TICKET = (
    '{"severity": "critical", "affected_services": ["checkout"], '
    '"description": "Checkout is down for all customers", '
    '"timestamp": "2025-11-28T09:14:00Z"}'
)
