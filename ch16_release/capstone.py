"""One model upgrade, end to end: a-large-v1 to a-large-v2.

Illustrative: the numbers come from invented traffic and an invented
eval set. The ladder is the point: gate, rehearsal, shadow, budget,
bundle, canary, and a rollback that is ready before it is needed.
"""
from dataclasses import dataclass
from functools import lru_cache

from common.clock import FakeClock
from ch12_slos.budget import budget_left
from ch16_release.bundle import Registry, make_bundle
from ch16_release.canary import GUARDS, Canary
from ch16_release.faulty import run_experiment
from ch16_release.policy import Change, release_check
from ch16_release.relay_parts import PROMPT_V14, PROMPT_V15, contents
from ch16_release.scorecard import api_cost
from ch16_release.shadow import shadow
from ch16_release.traffic import (CONTROL, V2_TUNED, V2_UNTUNED,
                                  make_chats)

BASELINE = {"quality": 0.91, "first_pass": 0.985,
            "p95_first_token": 1.40, "cost": api_cost(6.0, 5000)}
# how far a candidate may move from today's numbers
RULES = {"quality": lambda new, old: new >= old - 0.01,
         "first_pass": lambda new, old: new >= 0.98,
         "p95_first_token": lambda new, old: new <= old * 1.10,
         "cost": lambda new, old: new <= old * 1.15}
MEASURED = {   # offline, on the eval set: v2 is faster, cheaper, worse
    "a-large-v2, prompt v14": {"quality": 0.86, "first_pass": 0.991,
                               "p95_first_token": 1.10,
                               "cost": api_cost(4.6, 5000)},
    "a-large-v2, prompt v15": {"quality": 0.91, "first_pass": 0.990,
                               "p95_first_token": 1.10,
                               "cost": api_cost(4.6, 5400)}}
VERSIONS = {  # name: (behaviour, prompt text, prompt label, bundle id)
    "a-large-v2, prompt v14": (V2_UNTUNED, PROMPT_V14, "prompt v14",
                               "R-118"),
    "a-large-v2, prompt v15": (V2_TUNED, PROMPT_V15, "prompt v15",
                               "R-119")}
WRONG_POLICY = next(g for g in GUARDS if g.flag == "wrong_policy")


@dataclass
class Rung:
    name: str
    says: str          # "pass", "STOP", or "wait": the next rung decides
    detail: str

    @property
    def passed(self):
        return self.says != "STOP"


def rung(name, ok, detail):
    return Rung(name, "pass" if ok else "STOP", detail)


def eval_gate(metrics, baseline=BASELINE):
    """A stand-in for Chapter 15's gate: four point limits of its own.

    Chapter 15's real gate puts a paired interval on quality.
    """
    failed = [m for m, ok in RULES.items() if not ok(metrics[m], baseline[m])]
    if failed:
        m = failed[0]
        return rung("eval gate", False,
                    f"blocked on {m}: {metrics[m]:.2f} "
                    f"against {baseline[m]:.2f}")
    return rung("eval gate", True, f"all {len(RULES)} limits met")


@lru_cache(maxsize=None)
def rehearsal():
    """Last section's fault experiment, with failover on (same seed)."""
    return run_experiment(failover=True)


def shadow_rung(candidate, n=3000):
    """The canary's margin rule, on the shadow's paired interval.

    Half an hour of traffic: on 2,000 chats (171 graded) the tuned
    prompt's interval could not clear the 3-point margin either way.
    """
    r = shadow(make_chats(n), CONTROL, candidate, "wrong_policy")
    lo, hi = r.interval
    says = ("STOP" if lo > WRONG_POLICY.margin
            else "pass" if hi <= WRONG_POLICY.margin else "wait")
    return Rung("shadow", says,
                f"wrong policy {100 * r.diff:+.1f} points "
                f"({100 * lo:+.1f} to {100 * hi:+.1f}), {r.n} graded")


def upgrade(name, left, registry, stop=True):
    """Walk one candidate up the ladder. `stop=False` keeps going past a
    failed rung, to show what each later rung would have caught."""
    version, prompt, label, bundle_id = VERSIONS[name]
    rungs = [eval_gate(MEASURED[name])]
    drill = rehearsal()
    rungs.append(rung("rehearsal", drill.holds,
                      f"availability {drill.availability:.1%}"))
    rungs.append(shadow_rung(version))
    change = Change("model", name)
    verdict, why = release_check(change, left)
    rungs.append(rung("error budget", verdict == "ship", why))
    old = registry.live
    new = make_bundle(bundle_id, contents(prompt, "a-large-v2", label),
                      old.eval_set, old.judge)
    rungs.append(rung("bundle", True,
                      f"{new.id} {new.fingerprint()}, back to {old.id}"))
    if stop and not all(r.passed for r in rungs):
        return rungs, None
    result = Canary(CONTROL, version, FakeClock()).run()
    rungs.append(rung("canary", result.decision == "promoted",
                      f"{result.decision} at minute {result.minutes}: "
                      f"{result.reason}"))
    if result.decision == "promoted":
        registry.promote(new)
    return rungs, result


def start():
    """Today: bundle R-117 is live, with a-large-v1 and prompt v14."""
    registry = Registry()
    registry.promote(make_bundle("R-117", contents(
        PROMPT_V14, "a-large-v1", "prompt v14"), "Relay-60 v3", "judge v2"))
    return registry


def month_left():
    """Chapter 12's example 28 days: 1,900 of 5,000 failed chats spent."""
    return budget_left(0.995, 1_000_000, 1_900)
