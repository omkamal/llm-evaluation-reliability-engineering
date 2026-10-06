"""Multi-window, multi-burn-rate alerts over an injected time series."""
from bisect import bisect_right
from dataclasses import dataclass, replace

from common.clock import FakeClock

SLO = 0.995                         # availability, 28-day window
MINUTE = 60
MIN_CHATS = 100                     # a long window needs this many chats


class Series:
    """Per-minute counts of (bad, total) chats, read through a clock.

    `record` stamps a bucket with the clock's time; `window` sums the
    buckets of the last N seconds. Nothing here reads the wall clock,
    so a three-day history costs no time.
    """

    def __init__(self, clock):
        self.clock = clock
        self.times = []
        self.bad = [0]              # running totals, one step behind
        self.total = [0]

    def record(self, bad, total):
        self.times.append(self.clock.now())
        self.bad.append(self.bad[-1] + bad)
        self.total.append(self.total[-1] + total)

    def window(self, seconds):
        first = bisect_right(self.times, self.clock.now() - seconds)
        end = len(self.times)
        return (self.bad[end] - self.bad[first],
                self.total[end] - self.total[first])


@dataclass(frozen=True)
class Rule:
    action: str                     # "page" or "ticket"
    burn: float                     # fire above this multiple
    long_s: int                     # the window that carries the damage
    short_s: int                    # the window that says it is still on


RULES = (
    Rule("page", 14.4, 3600, 300),
    Rule("page", 6.0, 21600, 1800),
    Rule("ticket", 1.0, 259200, 21600),
)


@dataclass(frozen=True)
class Decision:
    action: str                     # "page", "ticket" or "ok"
    rule: Rule = None
    long_burn: float = 0.0
    short_burn: float = 0.0


def window_burn(series, seconds, slo):
    """No chats is no burn: an outage before the counter is silent here.

    Pair these rules with a traffic-floor alert and deep checks.
    """
    if not 0 < slo < 1:
        raise ValueError("an SLO of 100% leaves no error budget to burn")
    bad, total = series.window(seconds)
    ratio = bad / total if total else 0.0
    return round(ratio / (1 - slo), 6)      # no flip on float noise


def alert_decision(series, slo=SLO, rules=RULES, min_chats=MIN_CHATS):
    """The first rule whose BOTH windows burn above its limit."""
    for rule in rules:
        if series.window(rule.long_s)[1] < min_chats:
            continue                # one failure in a dozen is not a fire
        long_burn = window_burn(series, rule.long_s, slo)
        short_burn = window_burn(series, rule.short_s, slo)
        if long_burn > rule.burn and short_burn > rule.burn:
            return Decision(rule.action, rule, long_burn, short_burn)
    return Decision("ok")


def long_window_only(rules=RULES):
    """The same rules with the short window removed."""
    return tuple(replace(r, short_s=r.long_s) for r in rules)


def healthy_history(minutes=4320, per_minute=100):
    """Three quiet days: a clock and a series with no failures."""
    clock = FakeClock()
    series = Series(clock)
    for _ in range(minutes):
        clock.sleep(MINUTE)
        series.record(0, per_minute)
    return clock, series


def failures_per_minute(per_minute, failure_rate):
    """Whole failed chats a minute; refuse a rate that rounds away."""
    bad = per_minute * failure_rate
    if abs(bad - round(bad)) > 1e-9:
        raise ValueError(f"{failure_rate:.2%} of {per_minute} chats is "
                         "not a whole number; raise per_minute")
    return round(bad)


def minutes_to_alert(failure_rate, per_minute=1000, limit=5760):
    """Minutes of steady failure before any rule fires, or None."""
    clock, series = healthy_history(per_minute=per_minute)
    bad = failures_per_minute(per_minute, failure_rate)
    for minute in range(1, limit + 1):
        clock.sleep(MINUTE)
        series.record(bad, per_minute)
        decision = alert_decision(series)
        if decision.action != "ok":
            return minute, decision
    return None, Decision("ok")


def minutes_to_clear(rules, outage_minutes=30, failure_rate=0.20,
                     per_minute=100, limit=5760):
    """Fail for a while, then recover. First and last minute of alert.

    Returns (first_alert_minute, minutes_after_recovery_it_clears), or
    (None, None) if no rule fires within `limit` minutes.
    """
    clock, series = healthy_history(per_minute=per_minute)
    bad = failures_per_minute(per_minute, failure_rate)
    first = None
    for minute in range(1, limit + 1):
        clock.sleep(MINUTE)
        failing = minute <= outage_minutes
        series.record(bad if failing else 0, per_minute)
        firing = alert_decision(series, rules=rules).action != "ok"
        if firing and first is None:
            first = minute
        if first and not failing and not firing:
            return first, minute - outage_minutes
    return None, None
