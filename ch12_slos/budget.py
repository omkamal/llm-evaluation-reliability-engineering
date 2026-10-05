"""The error budget, the burn rate, and the policy a budget drives."""

WINDOW_DAYS = 28            # the common window of Relay's SLO sheet


def error_budget(slo, volume):
    """Failures the SLO allows over `volume` events."""
    return round((1 - slo) * volume)


def burn_rate(bad, total, slo):
    """Observed error rate divided by the allowed one. 1.0 = on pace."""
    if not total:
        return 0.0
    return (bad / total) / (1 - slo)


def days_to_empty(burn, window_days=WINDOW_DAYS):
    """How long a full budget lasts if this burn rate never changes."""
    return window_days / burn


def share_spent(burn, hours, window_days=WINDOW_DAYS):
    """Share of the window's budget used by `hours` at this burn rate.

    This assumes traffic in those hours is typical for the window. A
    busier hour spends more chats, because burn is a ratio.
    """
    return burn * hours / (window_days * 24)


def budget_left(slo, volume, bad):
    """Fraction of the error budget still unspent (can go below zero)."""
    allowed = error_budget(slo, volume)
    return (allowed - bad) / allowed


def policy_rung(left):
    """What the team does at this budget level (see Chapter 16)."""
    if left <= 0:
        return "freeze risky releases"
    if left < 0.25:
        return "reliability fixes only"
    if left <= 0.50:
        return "ship, one risky change at a time"
    return "ship features"
