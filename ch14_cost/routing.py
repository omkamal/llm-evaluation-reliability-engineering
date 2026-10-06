"""Route inside the rules: Chapter 10 filters and ranks, cost last."""
from ch10_providers.catalog import NoEligibleProvider
from ch10_providers.ranking import Signals, rank
from ch10_providers.tiers import IRREVERSIBLE

LARGE = {"Provider A", "Provider B"}     # the large tier


def quiet(catalog):
    """No news from the adapters: health and speed score alike, so the
    cheapest provider with room wins (Chapter 10's tie rule)."""
    return {p.name: Signals(1.0, 1.0, 1.0) for p in catalog}


def route(catalog, req, planned_tools=(), signals=None):
    """The best provider allowed to serve this request.

    signals: Chapter 10's live health per provider; pass them in
    production. Without them every provider is assumed healthy.
    """
    # Chapter 10's rank: eligible, with room, breaker shut; cost last
    ranked = rank(catalog, req, signals or quiet(catalog))
    if set(planned_tools) & IRREVERSIBLE:
        # a step that cannot be undone never goes to the small tier
        ranked = [p for p in ranked if p.name in LARGE]
    if not ranked:
        raise NoEligibleProvider(req.region)   # degrade, do not relax
    return ranked[0].name
