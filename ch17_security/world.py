"""A small world for the security chapter: who is logged in and who owns
what. Every id and amount is invented for the book. The session is built
by code at login; the model never writes it and never sees the token."""
from dataclasses import dataclass

from ch02_trust_outputs.refund import Order

TOKENS = {"tok-17": "cust-17", "tok-31": "cust-31"}   # the login system


def new_orders():
    """A fresh copy per case: orders are never shared between trials."""
    return {
        "ORD-004829": Order("cust-17", 4_999),     # the customer, $49.99
        "ORD-004832": Order("cust-17", 12_000),    # the customer, $120.00
        "ORD-004831": Order("cust-31", 48_000),    # a stranger, $480.00
    }


@dataclass(frozen=True)
class Session:
    customer_id: str     # who is logged in, as the login system says
    verified: bool       # has this person proved who they are?


def authenticate(token, verified=True):
    """Return the session for a login token, or None for a stranger."""
    customer = TOKENS.get(token)
    return Session(customer, verified) if customer else None


@dataclass(frozen=True)
class ToolCall:
    """What the model proposes. `read_text` is what it had just read."""
    name: str
    args: dict
    read_text: str = ""
    claimed_customer: str = ""   # who the plan SAYS the customer is
