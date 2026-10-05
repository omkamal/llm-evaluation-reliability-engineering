"""Relay's ticket schema: one definition, three jobs (prompt, provider schema, validator)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SEVERITIES = ("low", "medium", "high", "critical")


class Ticket(BaseModel, extra="forbid"):
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="critical: checkout or login is down for everyone")
    affected_services: list[str] = Field(min_length=1)
    description: str = Field(min_length=1)
    timestamp: datetime = Field(
        description="ISO 8601 UTC, for example 2026-11-27T09:14:00Z")


# The Black Friday reply: perfectly valid JSON, and wrong in two ways.
BLACK_FRIDAY = (
    '{"severity": "urgent", "affected_services": [], '
    '"description": "Checkout is down for all customers", '
    '"timestamp": "2026-11-27T09:14:00Z"}'
)
GOOD_TICKET = (
    '{"severity": "critical", "affected_services": ["checkout"], '
    '"description": "Checkout is down for all customers", '
    '"timestamp": "2026-11-27T09:14:00Z"}'
)
