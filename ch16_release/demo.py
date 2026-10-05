"""Every Chapter 16 output.   python3 -m ch16_release.demo"""
import textwrap
from dataclasses import replace
from datetime import date

from ch12_slos.budget import error_budget
from common.clock import FakeClock
from ch16_release.bundle import (Registry, changed_parts, drift,
                                 make_bundle)
from ch16_release.canary import Canary, budget_at_risk
from ch16_release.capstone import month_left, start, upgrade
from ch16_release.faulty import run_experiment
from ch16_release.lifecycle import migration_plan, notice_days
from ch16_release.policy import Change, release_check
from ch16_release.relay_parts import PROMPT_V14, PROMPT_V15, contents
from ch16_release.scorecard import (Candidate, api_cost, breakeven_tasks,
                                    choose, self_hosted_cost, table)
from ch16_release.shadow import shadow
from ch16_release.traffic import (CONTROL, FRIDAY, V2_UNTUNED, make_chats)


def demo_friday():
    print("== Friday's tweak, first at 5 percent")
    res = Canary(CONTROL, FRIDAY, FakeClock()).run()
    print(f"{res.decision} at minute {res.minutes}: {res.reason}")
    print(f"the canary served {res.exposed} chats; reschedules nobody "
          f"asked for: {res.unasked}")
    everyone = make_chats(res.minutes * 100)
    unasked = sum(FRIDAY.serve(c).unasked for c in everyone)
    print(f"all chats on the tweak for those {res.minutes} minutes: "
          f"{unasked}")


def pct(x):
    return f"{x:.1%}"


def p_text(p):
    return "p < 0.0001" if p < 0.0001 else f"p = {p:.4f}"


def demo_shadow():
    print("== shadow: the Friday tweak on 2,000 live chats")
    chats = make_chats(2000)
    r = shadow(chats, CONTROL, FRIDAY, "acted")
    lo, hi = r.interval
    print(f"reschedule share: old {pct(r.old_rate)}, new {pct(r.new_rate)}")
    print(f"paired difference {r.diff:+.3f} ({lo:.3f} to {hi:.3f})")
    print(f"chats that differ: {pct(r.disagree)}; new acts only: "
          f"{r.worse}, old acts only: {r.better}")
    print(f"sign test on those chats: {p_text(r.p_flips)}")
    print(f"first chats to read: {', '.join(map(str, r.examples))}")
    print("== shadow: a-large-v2 with prompt v14, wrong policy answers")
    r = shadow(chats, CONTROL, V2_UNTUNED, "wrong_policy")
    print(f"graded {r.n} of {len(chats):,} chats: old {pct(r.old_rate)}, "
          f"new {pct(r.new_rate)}")
    print(f"new wrong only: {r.worse}, old wrong only: {r.better}, "
          f"sign test {p_text(r.p_flips)}")


def demo_canary():
    print("== three canaries")
    flaky = replace(CONTROL, name="flaky candidate", p_fail=0.08)
    print(f"{'candidate':<14}{'result':<12}{'minute':>6}{'chats':>6}  why")
    for label, cand in (("Friday tweak", FRIDAY), ("8% errors", flaky),
                        ("unchanged", CONTROL)):
        res = Canary(CONTROL, cand, FakeClock()).run()
        print(f"{label:<14}{res.decision:<12}{res.minutes:>6}"
              f"{res.exposed:>6}  {res.reason}")
        if cand is flaky:
            burn = res
    allowed = error_budget(0.995, 1_000_000)
    small = budget_at_risk(0.05, burn.minutes, 100, 0.08)
    big = budget_at_risk(1.0, burn.minutes, 100, 0.08)
    print(f"{burn.minutes} minutes at 8% errors: {small} failed chats at "
          f"5%, {big} at 100%")
    print(f"share of the {allowed:,}-chat error budget: "
          f"{small / allowed:.1%} against {big / allowed:.1%}")
    runs = [Canary(CONTROL, CONTROL, FakeClock(), seed=s).run(limit=480)
            for s in range(10)]
    rolled = sum(r.decision == "rolled back" for r in runs)
    print(f"control against itself, 10 seeds: {rolled} rolled back")


def demo_faulty():
    print("== rehearse failure: 2,000 chats, faults on")
    for label, failover in (("run 1", False),
                            ("run 2, failover to B", True)):
        run = run_experiment(failover=failover)
        verdict = "holds" if run.holds else "hypothesis broken"
        print(f"{label}: {run.availability:.1%} available "
              f"({len(run.failed)} of {run.chats:,} failed): {verdict}")
        print(f"  first token within 2 s: {run.first_token_rate:.1%}; "
              f"partial-JSON tool calls run: {run.ran_from_partial}")
        if not failover:
            print("  injected:", ", ".join(
                f"{k} {v}" for k, v in run.injected.items()))
    stress = run_experiment(faults={"rate_limited": 0.30, "timeout": 0.02},
                            abort_below=0.9)
    print(f"abort at chat {stress.chats}: {stress.aborted}")


def demo_policy():
    print("== the error-budget check")
    model = Change("model", "a-large-v1 to a-large-v2")
    fix = Change("reliability_fix", "fail over when retries run out")
    rows = [(model, 0.62, 0), (model, 0.36, 1), (model, 0.22, 0),
            (fix, 0.22, 0), (model, 0.0, 0)]
    for change, left, flight in rows:
        decision, why = release_check(change, left, flight)
        print(f"{change.kind:<16}{left:>4.0%} left  {decision:<5} {why}")


def demo_bundle():
    print("== the release bundle")
    old = make_bundle("R-117", contents(PROMPT_V14, "a-large-v1",
                      "prompt v14"), "Relay-60 v3", "judge v2")
    new_parts = contents(PROMPT_V15, "a-large-v2", "prompt v15")
    new = make_bundle("R-118", new_parts, "Relay-60 v3", "judge v2")
    print(f"{old.id} fingerprint {old.fingerprint()}")
    for part, (label, short) in old.parts.items():
        print(f"  {part:<8}{label:<20}{short}")
    print(f"{new.id} fingerprint {new.fingerprint()}, "
          f"{len(changed_parts(old, new))} parts changed")
    for line in changed_parts(old, new):
        print(f"  {line}")
    live = {p: body for p, (_, body) in new_parts.items()}
    print(f"deployed matches {new.id}: {not drift(new, live)}")
    live["prompt"] += " Be more proactive."
    print(f"after a hand edit of the prompt: drift in {drift(new, live)}")
    registry = Registry()
    registry.promote(old)
    registry.promote(new)
    back = registry.roll_back()
    print(f"roll back: live {back.id}, fingerprint {back.fingerprint()}")


def demo_lifecycle():
    print("== a retirement notice")
    days = notice_days(date(2026, 9, 30), date(2026, 11, 30))
    print(f"notice 30 Sep, retirement 30 Nov: {days} days")
    for day, step in migration_plan(60):
        print(f"day {day:>2}: {step}")
    print("== the scorecard (invented numbers, 200 cases)")
    v2_cost = api_cost(4.6, 5000)
    fixed = 24_600
    candidates = [
        Candidate("a-large-v1", 182, api_cost(6.0, 5000), 1.4, 4, 30),
        Candidate("a-large-v2 p14", 172, v2_cost, 1.1, 20, 30),
        Candidate("a-large-v2 p15", 182, api_cost(4.6, 5400), 1.1, 20, 30),
        Candidate("a-small-v1", 156, api_cost(1.2, 6500), 0.7, 20, 30),
        Candidate("b-large (EU)", 182, api_cost(8.0, 5000), 1.5, 14, 0),
        Candidate("open-70b (ours)", 168,
                  self_hosted_cost(fixed, 0.004, 900_000), 1.9, 99, 0)]
    for line in table(candidates):
        print(line)
    print(f"choice: {choose(candidates).name}")
    print("== build or buy")
    even = breakeven_tasks(fixed, v2_cost, 0.004)
    print(f"break-even: {even:,.0f} tasks a month; ParcelPath runs "
          f"about 900,000")


def demo_capstone():
    allowed = error_budget(0.995, 1_000_000)
    print(f"error budget this month: {allowed - 1900:,} of {allowed:,} "
          f"failed chats left ({month_left():.0%})")
    for name, stop in (("a-large-v2, prompt v14", False),
                       ("a-large-v2, prompt v15", True)):
        print(f"== upgrade: {name}")
        registry = start()
        rungs, result = upgrade(name, month_left(), registry, stop)
        for r in rungs:
            line = f"{r.name:<13}{'pass' if r.passed else 'STOP':<5}{r.detail}"
            print(textwrap.fill(line, 74, subsequent_indent=" " * 18))
        print(f"live bundle: {registry.live.id}")
        if result and result.decision == "promoted":
            ramp = ", ".join(f"{share:.0%} to minute {m}"
                             for m, share in result.log)
            print(f"canary ramp: {ramp}")
            print(f"canary chats: {result.exposed:,}, failed: "
                  f"{result.failed}")
            drill = registry.roll_back()
            print(f"rollback drill: live {drill.id}, fingerprint "
                  f"{drill.fingerprint()}")


def main():
    for section in (demo_friday, demo_shadow, demo_canary, demo_faulty,
                    demo_policy, demo_bundle, demo_lifecycle,
                    demo_capstone):
        section()


if __name__ == "__main__":
    main()
