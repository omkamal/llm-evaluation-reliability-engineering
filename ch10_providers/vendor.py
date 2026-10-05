"""Arithmetic for reading a vendor's promises."""


def allowed_downtime_minutes(availability, days):
    """Minutes of outage a monthly availability figure permits."""
    return (1 - availability) * days * 24 * 60


def chained(a, b):
    """Availability of two independent providers with perfect failover."""
    return 1 - (1 - a) * (1 - b)
