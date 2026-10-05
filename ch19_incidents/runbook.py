"""A runbook is data: ordered rungs, each one flag flip, each followed
by the same probe. Climb only as high as the harm needs."""
from dataclasses import dataclass

from ch19_incidents.flags import resolve
from ch19_incidents.timeline import clock_text


@dataclass(frozen=True)
class Step:
    rung: int       # 1 disable tool, 2 approval, 3 pin, 4 kill switch
    what: str       # the words that go in the incident log
    flag: str
    value: object


class NotALadder(ValueError):
    pass


def check_ladder(steps):
    """Rungs may repeat but never step back down: narrow first."""
    rungs = [s.rung for s in steps]
    if rungs != sorted(rungs):
        raise NotALadder(f"rungs out of order: {rungs}")


def climb(steps, flags, probe, clock, who, log=print):
    """Flip one rung, re-run the probe, stop at the first clean one."""
    check_ladder(steps)
    for step in steps:
        flags.set(step.flag, step.value, who, step.what)
        clock.sleep(60)                  # a minute to flip and check
        left = probe(resolve(flags))
        verdict = ", ".join(left) + " still open" if left else "clean"
        log(f"{clock_text(clock.now())} rung {step.rung} "
            f"{step.what}: {verdict}")
        if not left:
            return step
    return None          # even the top rung left something: call for help


INC6_RUNBOOK = [
    Step(1, "disable issue_refund", "disabled_tools", ("issue_refund",)),
    Step(3, "pin bundle 2026.08.25", "bundle", "2026.08.25"),
    Step(4, "kill switch on", "kill_switch", True),
]
