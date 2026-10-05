"""Simulated incident data: illustrative, drawn from Figure 10.4."""

# (minute, error rate in percent) of Provider A, a schematic outage
CURVE = [(0, 2), (3, 2.5), (5, 4), (6, 11), (7, 20), (8, 29), (10, 36),
         (12, 34), (14, 30), (16, 22), (17, 15), (19, 12), (21, 17),
         (23, 10.5), (25, 8), (26.3, 5), (28, 2.5), (31, 2), (35, 1.5),
         (36.5, 2.8), (38, 1.6), (45, 1.5)]


def error_curve(tick=6):
    """(seconds, error %) every `tick` seconds, straight lines between."""
    pts = [(round(m * 60), e) for m, e in CURVE]
    for (t0, e0), (t1, e1) in zip(pts, pts[1:]):
        for t in range(t0, t1, tick):
            yield t, e0 + (e1 - e0) * (t - t0) / (t1 - t0)
    yield pts[-1]


def rank_first(catalog, signals):
    """The mistake: pick the best score among whoever has room."""
    from ch10_providers.ranking import score
    room = [p for p in catalog if p.free_slots > 0]
    return max(room, key=lambda p: score(p, signals[p.name]))
