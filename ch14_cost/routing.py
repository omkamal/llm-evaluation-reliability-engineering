"""Route by price, only inside the rules: filter first, rank second."""
from ch10_providers.catalog import NoEligibleProvider, eligible
from ch10_providers.tiers import IRREVERSIBLE

LARGE = {"Provider A", "Provider B"}     # the large tier


def route(catalog, req, planned_tools=()):
    """The cheapest provider that is allowed to serve this request."""
    pool = eligible(catalog, req)    # residency, context, tools, policy
    if set(planned_tools) & IRREVERSIBLE:
        # a step that cannot be undone is never routed by price alone
        pool = [p for p in pool if p.name in LARGE]
    if not pool:
        raise NoEligibleProvider(req.region)   # degrade, do not relax
    return min(pool, key=lambda p: p.cost).name
