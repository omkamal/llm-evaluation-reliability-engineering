"""One strict schema per tool. Strict: nothing is converted ("4999" and
true are refused). Closed: an extra field fails, so the model cannot add
a customer_id, or a second order id, to any tool, not only the refund."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from ch02_trust_outputs.schema import Text

# ASCII digits only: \d also matches other scripts' digits
OrderId = Annotated[str, Field(pattern=r"^ORD-[0-9]{6}$")]


class Args(BaseModel, extra="forbid", strict=True):
    pass


class OrderArgs(Args):
    order_id: OrderId


class PolicyArgs(Args):
    topic: Text


class RescheduleArgs(Args):
    order_id: OrderId
    window: Text


class ResetArgs(Args):
    user: Text


class IncidentArgs(Args):
    id: Text
    priority: Literal["P1", "P2", "P3", "P4"]
    group: Text


class HandoffArgs(Args):
    reason: Text
    context_packet: Text

