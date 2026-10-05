"""The gate suite: Relay-30 and Relay-60 as one list of 90 cases.

The scripted verdicts (which cases a build gets right) come from the real
graders of Chapters 3 and 6. The noise on top is Chapter 4's simulation:
the chances below are ILLUSTRATIVE, not a measurement of any model.

A build is one of two scripted Relays:
  main    Chapter 3's v1 on the policy cases, Chapter 6's `current`
  friday  Chapter 3's v2 on the policy cases, Chapter 6's `candidate`
          (both are the "be more proactive" tweak of INC-2)
"""
import random
from functools import lru_cache

from ch03_first_eval.cases import CASES as POLICY
from ch03_first_eval.run_evals import run as run_policy
from ch04_numbers.noisy import LUCKY, STAY_RIGHT
from ch06_agents.cases import RELAY_60
from ch06_agents.compare import outcomes
from ch06_agents.relays import candidate, current

BORDERLINE = {"R-12": 0.55, "R-26": 0.55, "T1.6": 0.55, "T6.6": 0.55}
# Four cases whose phrasing sits on the line between right and wrong:
# a build gets them right about half the time. Real suites have such
# cases; they are what makes an eval flaky.


def case_meta():
    """Every case, in order: id, slice, text and the never-fail flag."""
    meta = [{"id": c["id"], "slice": "policy", "text": c["question"],
             "never_fail": False} for c in POLICY]
    for c in RELAY_60:
        meta.append({
            "id": c["id"], "text": c["message"],
            "slice": "trigger" if c["should_act"] else "non-trigger",
            # T3: reset a password for someone who is not verified.
            "never_fail": c["type"] == "T3"})
    return meta


@lru_cache(maxsize=None)
def scripted(build):
    """1 where the scripted build gets the case right, else 0."""
    versions = {"main": ("v1", current), "friday": ("v2", candidate)}
    policy_version, agent = versions[build]
    right = [int(ok) for _, ok, _ in run_policy(policy_version)]
    return tuple(right + outcomes(agent, RELAY_60))


def chance(case, right):
    """Chance of passing one trial of this case."""
    if case["id"] in BORDERLINE:
        return BORDERLINE[case["id"]]
    if right:
        # Never-fail cases are checked in the sandbox (Chapter 6) and a
        # correct Relay passes them every time.
        return 1.0 if case["never_fail"] else STAY_RIGHT
    return LUCKY


def run_trials(build, trials, rng, ids=None, safety_trials=None):
    """results[id] = {slice, never_fail, trials: [0/1, ...]}."""
    out = {}
    for case, right in zip(case_meta(), scripted(build)):
        if ids is not None and case["id"] not in ids:
            continue
        n = safety_trials if case["never_fail"] and safety_trials \
            else trials
        p = chance(case, right)
        out[case["id"]] = {
            "slice": case["slice"], "never_fail": case["never_fail"],
            "trials": [int(rng.random() < p) for _ in range(n)]}
    return out


def paired_outcomes(better, worse, n=200, passes=159):
    """Constructed outcomes for a worked example: `n` cases, `passes` of
    them right on main, `better` fixed and `worse` broken by the change.
    Returns (main, change) in the format the gate reads."""
    main = [1] * passes + [0] * (n - passes)
    change = main[:]
    for i in range(worse):
        change[i] = 0
    for i in range(better):
        change[passes + i] = 1
    wrap = lambda rows: {f"c{i:03d}": {"slice": "all", "never_fail": False,
                                       "trials": [v]}
                         for i, v in enumerate(rows)}
    return wrap(main), wrap(change)


def rng_for(seed):
    return random.Random(seed)
