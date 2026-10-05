"""Who is told what, how fast, and whether the alert was worth it."""
from statistics import median

from ch13_drift.bands import first_alert, mean_band, rate_band
from ch13_drift.relay_sim import SIGNALS, nine_days


def alert_day(signal, series, k=2):
    """First day after the rebuild when a person hears about it.

    `series` covers days -14 to 9. A signal that needs `lag` days to be
    known (a reopen window) reaches people that many days late.
    """
    lo, hi = (mean_band(signal.base, signal.sd, signal.n) if signal.sd
              else rate_band(signal.base, signal.n))
    after = series[14:]                        # days 0 to 9
    flags = [v < lo if signal.bad == "down" else v > hi for v in after]
    i = first_alert(flags[1:], k)              # skip day 0
    return None if i is None else i + 1 + signal.lag


def median_alert_days(runs=500):
    """Median first-alert day per signal, over simulated replays."""
    found = {s.name: [] for s in SIGNALS}
    for seed in range(runs):
        replay = nine_days(seed)
        for s in SIGNALS:
            day = alert_day(s, replay[s.name])
            if day is not None:
                found[s.name].append(day)
    return {name: (median(days), len(days))
            for name, days in found.items()}


def route(touches_money_or_safety, persistent, enough_data=True):
    """Page, ticket or dashboard. Persistence guards the page."""
    if not (persistent and enough_data):
        return "dashboard"
    return "page" if touches_money_or_safety else "ticket"


def group_incidents(alerts, window=2):
    """Alerts for one segment less than `window` hours apart are one."""
    last, incidents = {}, []
    for hour, segment in sorted(alerts):
        if segment in last and hour - last[segment][-1] <= window:
            last[segment].append(hour)
        else:
            last[segment] = [hour]
            incidents.append(last[segment])
        # each list in `incidents` is shared with `last`, so it grows
    return incidents


# An invented month of alerts: rule, route it used, fired, acted on.
ALERT_LOG = [
    ("refund share up, 2 windows", "page", 2, 2),
    ("good rate down, 1 window", "page", 11, 2),
    ("good rate down, 2 windows", "ticket", 4, 3),
    ("tool-mix PSI over 0.25", "ticket", 5, 4),
    ("answer-length PSI over 0.1", "ticket", 7, 0),
]


def review(log, bar=0.5):
    """Per rule: precision (acted / fired) and what to do about it."""
    rows = []
    for rule, where, fired, acted in log:
        precision = acted / fired
        verdict = "keep" if precision >= bar else "tighten"
        rows.append((rule, where, fired, acted, precision, verdict))
    return rows
