"""A tool call is a request from a stranger. Four layers of checks stand between it and the payments system."""
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

AUTO_LIMIT_CENTS = 5_000     # refunds up to $50 are automatic; above that a person approves


class RefundArgs(BaseModel, extra="forbid"):
    order_id: str = Field(pattern=r"^ORD-\d{6}$")
    amount_cents: int = Field(gt=0)
    reason: Literal["damaged", "late", "other"]


@dataclass
class Order:
    customer_id: str
    total_cents: int
    refunded_cents: int = 0


@dataclass
class ToolError:
    layer: str               # schema | referential | authorization | business
    code: str
    message: str             # written for the model: it tells it what to fix


ORDERS = {"ORD-004829": Order("cust-17", 4_999),
          "ORD-004830": Order("cust-22", 12_000)}


def validate_refund_args(raw, user_id, orders=ORDERS):
    # layer 1: schema
    try:
        args = RefundArgs.model_validate(raw)
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(map(str, first["loc"]))
        return ToolError("schema", "invalid_arguments",
                         f"{where}: {first['msg']}")
    # layer 2: referential
    order = orders.get(args.order_id)
    if order is None:
        return ToolError("referential", "order_not_found", args.order_id)
    # layer 3: authorization
    if order.customer_id != user_id:
        return ToolError("authorization", "not_authorized",
                         "not your order")
    # layer 4: business rule
    left = order.total_cents - order.refunded_cents
    if args.amount_cents > left:
        return ToolError("business", "amount_too_high",
                         f"max {left} cents")
    return args


def needs_approval(args):
    return args.amount_cents > AUTO_LIMIT_CENTS
