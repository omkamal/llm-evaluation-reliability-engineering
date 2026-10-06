"""Evals run against a test tenant with seeded fake data, never live."""
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Tenant:
    name: str
    kind: str                       # "test" or "live"


class LiveTenantError(RuntimeError):
    pass


def require_test_tenant(tenant):
    """The first line of every eval run."""
    if tenant.kind != "test" or not tenant.name.startswith("eval-"):
        raise LiveTenantError(
            f"refusing to run evals against {tenant.name!r}")


def seed_orders(seed=1, n=3):
    """Fake orders in a reserved id range that real orders never use."""
    rng = random.Random(seed)
    return [{"order_id": f"ORD-9{i:05d}", "customer": f"Test Customer {i}",
             "total_cents": rng.choice([1999, 4999, 7500]),
             "status": "out_for_delivery"} for i in range(1, n + 1)]


def bind_orders(text, orders):
    """A redacted case says <ORDER_1>, which no tenant can look up:
    give each placeholder a seeded order, so the case can run."""
    for n, order in enumerate(orders, 1):
        text = text.replace(f"<ORDER_{n}>", order["order_id"])
    if "<ORDER_" in text:
        raise ValueError("the case names more orders than were seeded")
    return text
