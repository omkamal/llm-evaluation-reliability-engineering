"""Rubber-stamping, simulated and detected. The rates are invented.

One reviewer reads carefully, then (after case `stamp_after`) approves
everything in seconds. Four signals are watched: the override rate, the
catch rate on seeded known-bad cases, the time per case, and kappa
against a careful second reviewer.
"""
import random
from dataclasses import dataclass
from statistics import median

from ch05_judge.agreement import cohen_kappa

CATCH, FALSE_FLAG = 0.90, 0.03       # a careful reviewer, per case


@dataclass
class Decision:
    n: int
    probe: bool         # a seeded, known-bad proposal
    bad: bool           # the proposal should not go out as it is
    verdict: str        # approve | reject
    seconds: float


def careful(rng, bad):
    """One careful reading: (verdict, seconds)."""
    flagged = rng.random() < (CATCH if bad else FALSE_FLAG)
    return ("reject" if flagged else "approve",
            max(5.0, rng.gauss(40, 8)))


def simulate(n=400, bad_rate=0.08, probe_every=20, stamp_after=None,
             seed=18):
    """A shift of review decisions, plus a careful second opinion."""
    rng, second = random.Random(seed), random.Random(seed + 1)
    first, other = [], []
    for i in range(n):
        probe = (i + 1) % probe_every == 0
        bad = probe or rng.random() < bad_rate
        if stamp_after is not None and i >= stamp_after:
            verdict, secs = "approve", max(1.0, rng.gauss(4, 1))
        else:
            verdict, secs = careful(rng, bad)
        first.append(Decision(i, probe, bad, verdict, secs))
        other.append(careful(second, bad)[0])
    return first, other


def window_report(decisions, other):
    """The signals for one window of decisions."""
    probes = [d for d in decisions if d.probe]
    caught = sum(d.verdict == "reject" for d in probes)
    kappa = cohen_kappa([d.verdict for d in decisions], other)
    return {
        "override": sum(d.verdict == "reject" for d in decisions)
        / len(decisions),
        "probes": (caught, len(probes)),
        "median_s": median(d.seconds for d in decisions),
        "kappa": kappa,
    }


def flags(report, min_override=0.02, min_catch=0.7, min_seconds=10):
    """Which signals say 'nobody is reading'? Tune these on a healthy
    month of your own."""
    caught, seeded = report["probes"]
    out = []
    if report["override"] < min_override:
        out.append("override")
    if seeded and caught / seeded < min_catch:
        out.append("probes")
    if report["median_s"] < min_seconds:
        out.append("speed")
    return out
