"""The guard chain: cheap, deterministic layers first; a model-based
screen, if you run one, comes last. Each layer returns None (no opinion)
or a Decision. The first deny wins."""
from dataclasses import dataclass, field

from pydantic import ValidationError

from ch02_trust_outputs.refund import RefundArgs
from ch10_providers.tiers import ActionBlocked, guard_tool
from ch17_security.policy import RULES
from ch17_security.world import new_orders


@dataclass(frozen=True)
class Decision:
    verdict: str     # "allow", "approve" (a person decides) or "deny"
    layer: str       # which layer spoke
    reason: str


def on_the_belt(call, ctx):
    if call.name not in RULES:
        return Decision("deny", "belt", f"{call.name} is not a tool")


def service_tier(call, ctx):
    try:                          # Chapter 10's service-tier guard
        guard_tool(call.name, ctx.service_tier, ctx.blocked)
    except ActionBlocked as err:
        return Decision("deny", "tier", str(err))


def well_formed(call, ctx):
    if call.name != "issue_refund":
        return None
    try:                          # Chapter 2's schema: extra fields fail
        RefundArgs.model_validate(call.args)
    except ValidationError as err:
        return Decision("deny", "schema", err.errors()[0]["msg"])


def verified_session(call, ctx):
    rule = RULES.get(call.name)
    if rule and rule.verified and not ctx.session.verified:
        return Decision("deny", "session", "verify the customer first")


def check_owner(call, ctx, asker):
    """The record's owner is looked up by code; `asker` says whose
    session this is. Everything depends on where `asker` comes from."""
    rule = RULES.get(call.name)
    if not rule:
        return None
    if rule.self_arg and call.args.get(rule.self_arg) != asker:
        return Decision("deny", "owner", "account is not yours")
    if not rule.owned:
        return None
    order = ctx.orders.get(call.args.get(rule.owned))
    if order is None:
        return Decision("deny", "owner", "no such order")
    if order.customer_id != asker:
        return Decision("deny", "owner", "order is not yours")


def owner_from_session(call, ctx):
    """The asker is the login session: a fact code established."""
    return check_owner(call, ctx, ctx.session.customer_id)


def owner_from_plan(call, ctx):
    """The INC-6 bug: the asker is whoever the model's plan names."""
    return check_owner(call, ctx, call.claimed_customer)


def within_limits(call, ctx):
    rule = RULES.get(call.name)
    cap = rule.auto_cents if rule else 0
    if not cap:
        return None
    try:
        args = RefundArgs.model_validate(call.args)
    except ValidationError:
        return None               # the schema layer's business
    order = ctx.orders.get(args.order_id)
    if order is None:
        return None               # the owner layer's business
    left = order.total_cents - order.refunded_cents
    if args.amount_cents > left:
        return Decision("deny", "limit", f"max {left} cents")
    if args.amount_cents > cap:
        return Decision("approve", "limit", f"above {cap} cents")


def model_screen(screen):
    """Wrap a text classifier as a layer. It sees what the model read."""
    def layer(call, ctx):
        if screen(call.read_text):
            return Decision("deny", "screen", "looks like an injection")
    return layer


# the order matters: cheap and decisive layers first
LAYERS = {"belt": on_the_belt, "tier": service_tier,
          "schema": well_formed, "session": verified_session,
          "owner": owner_from_session, "limit": within_limits}
DETERMINISTIC = list(LAYERS.values())
# the same chain with the owner taken from the model's plan
NAIVE = [owner_from_plan if layer is owner_from_session else layer
         for layer in DETERMINISTIC]
# a reconstruction of INC-6: right tool, well-formed call, owner from
# the plan, and nothing else
INC6 = [on_the_belt, well_formed, owner_from_plan]


@dataclass
class Ctx:
    session: object
    orders: dict = field(default_factory=new_orders)
    service_tier: int = 1
    layers: list = field(default_factory=lambda: list(DETERMINISTIC))
    blocked: list = field(default_factory=list)


def decide(call, ctx):
    """Run the layers in order; a deny stops the chain, an approve waits
    for the rest to speak, and silence from every layer means allow."""
    pending = None
    for layer in ctx.layers:
        found = layer(call, ctx)
        if found is None:
            continue
        if found.verdict == "deny":
            return found
        pending = pending or found
    return pending or Decision("allow", "chain", "every layer passed")
