"""Simulated Relay data for the drift examples.

EVERYTHING HERE IS ILLUSTRATIVE: invented to show a method, not measured
on any real system. Seeds are fixed, so every run prints the same numbers.
"""
import random
from dataclasses import dataclass
from math import log, sqrt

TOOLS = ["lookup_order", "lookup_policy", "reschedule_delivery",
         "issue_refund", "escalate_to_human"]
BASE_MIX = (0.42, 0.30, 0.18, 0.03, 0.07)    # the last 28 days


@dataclass(frozen=True)
class Segment:
    name: str
    seed: int           # chosen so the sampled PSI matches Figure 13.3
    calls_base: int     # tool calls in the 28-day baseline
    calls_now: int      # tool calls this week
    mix_now: tuple      # this week's tool mix
    share: float        # share of the week's conversations
    base_good: float    # baseline good-answer rate for the segment
    good_now: float     # this week's true good-answer rate


SEGMENTS = [
    Segment("web chat", 2, 48000, 12000,
            (0.336, 0.351, 0.180, 0.030, 0.103), 0.44, 0.93, 0.927),
    Segment("mobile chat", 2, 24000, 6000,
            (0.321, 0.300, 0.279, 0.030, 0.070), 0.25, 0.91, 0.908),
    Segment("US email", 2, 12000, 3000,
            (0.263, 0.418, 0.180, 0.030, 0.109), 0.14, 0.88, 0.879),
    Segment("EU chat", 2, 10000, 2500,
            (0.236, 0.447, 0.180, 0.030, 0.107), 0.09, 0.90, 0.900),
    Segment("EU email", 5, 6000, 1500,
            (0.204, 0.435, 0.153, 0.030, 0.178), 0.08, 0.80, 0.660),
]


def week_of_conversations(seed=4, total=20000):
    """One week of conversations, each with the verdict a calibrated
    judge WOULD give it (only the 5% sample is ever judged)."""
    rng = random.Random(seed)
    rows = []
    for i in range(total):
        seg = rng.choices(SEGMENTS, [s.share for s in SEGMENTS])[0]
        rows.append({"id": f"C-{i:05d}", "segment": seg.name,
                     "verdict": ("pass" if rng.random() < seg.good_now
                                 else "fail")})
    return rows


def tool_calls(seg):
    """(baseline calls, this week's calls) for one segment."""
    rng = random.Random(seg.seed)
    base = rng.choices(TOOLS, BASE_MIX, k=seg.calls_base)
    now = rng.choices(TOOLS, seg.mix_now, k=seg.calls_now)
    return base, now


def input_chars(median, n, rng, sigma=0.6):
    """Message lengths in characters, log-normal as lengths tend to be."""
    mu = log(median)       # the median of a log-normal is e**mu
    return [rng.lognormvariate(mu, sigma) for _ in range(n)]


def weekly_decay(seed, n=1000, base=0.91, slope=0.005, start=6,
                 weeks=16):
    """One segment's weekly good-answer rate: steady, then a slow slide.

    Same recipe as Figure 13.2: half a point a week from week 6.
    """
    rng = random.Random(seed)
    rates = []
    for week in range(1, weeks + 1):
        p = base - slope * max(0, week - start)
        rates.append(rng.gauss(p, sqrt(p * (1 - p) / n)))
    return rates


@dataclass(frozen=True)
class Signal:
    name: str
    kind: str          # leading or lagging
    base: float
    end: float         # where it is nine days after the rebuild
    n: int             # observations per day
    sd: float = 0.0    # spread of one observation, for averages
    lag: int = 0       # days before a day's value is known
    bad: str = "down"  # which direction hurts


SIGNALS = [
    Signal("steps per task", "leading", 4.0, 4.5, 30000, sd=1.6,
           bad="up"),
    Signal("good-answer rate", "lagging", 0.91, 0.86, 1500),
    Signal("first-contact resolution", "lagging", 0.81, 0.64, 30000,
           lag=3),
]


def nine_days(seed, days=range(-14, 10)):
    """Daily values of each signal around the rebuild (day 0).

    A slide, not a cliff: each signal moves in a straight line from its
    baseline to its day-9 value, plus the noise of measuring it.
    """
    rng = random.Random(seed)
    out = {}
    for s in SIGNALS:
        series = []
        for d in days:
            true = s.base + (s.end - s.base) * min(max(d, 0), 9) / 9
            sd = s.sd or sqrt(true * (1 - true))   # one observation
            se = sd / sqrt(s.n)
            series.append(rng.gauss(true, se))
        out[s.name] = series
    return out
