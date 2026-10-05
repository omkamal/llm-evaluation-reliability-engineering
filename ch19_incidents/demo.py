"""Every Chapter 19 output.   python3 -m ch19_incidents.demo"""
import json
from datetime import date

from ch06_agents.sandbox import new_state, ord_id
from ch11_traces.tracer import IdGenerator, Tracer
from ch13_drift.bands import rate_band
from common.clock import FakeClock
from ch19_incidents import compensate as comp
from ch19_incidents.comms import StatusUpdate, lint
from ch19_incidents.declare import (Incident, declare_reasons, response,
                                    severity)
from ch19_incidents.flags import (CURRENT, LAST_GOOD, FlagStore, resolve)
from ch19_incidents.postmortem import (ActionItem, Factor, Postmortem,
                                       cases_added, closed_share,
                                       problems)
from ch19_incidents.recovery import can_close
from ch19_incidents.runbook import INC6_RUNBOOK, climb
from ch19_incidents.standin import (NOTE_CASES, credit_under_limit_works,
                                    harm_probe, attempt)
from ch19_incidents.timeline import (Scribe, at, durations, merge, render,
                                     trace_rows)


def inc6_clock():
    """INC-6 on the one clock: a trace for the machine side, the scribe's
    log for the people side. The people lines are what the incident
    log would say; times are the incident's (RELAY-FACTS)."""
    clock = FakeClock(at("14:02"))
    tracer = Tracer(clock, IdGenerator(seed=6))
    with tracer.span("invoke_agent Planner", "agent", attrs={
            "gen_ai.conversation.id": "c-7731"}):
        clock.sleep(60)
        args = {"order_id": ord_id(1), "amount_cents": 40000,
                "reason": "other"}
        with tracer.span("execute_tool issue_refund", "tool", attrs={
                "gen_ai.tool.name": "issue_refund", "relay.tool.tier": 2,
                "relay.tool.args": json.dumps(args, sort_keys=True)}):
            clock.sleep(2)
    scribe = Scribe(clock)
    rows = trace_rows(tracer.finished)
    marks = {"arrived": rows[0][0], "harm": rows[1][0]}
    for hhmm, text, mark in (
            ("14:40", "Finance flags the credit; incident declared",
             "declared"),
            ("14:52", "a feature flag disables credits", "braked"),
            ("15:10", "last good bundle pinned; guard to review",
             "contained")):
        clock.t = at(hhmm)
        scribe.note(text, mark)
    return merge(rows, scribe.rows), {**marks, **scribe.marks}


def demo_clock():
    print("== INC-6 on one clock")
    rows, marks = inc6_clock()
    print("\n".join(render(rows)))
    for name, minutes in durations(marks).items():
        print(f"{name}: {minutes} min")


def demo_declare():
    print("== declare and classify")
    print(declare_reasons(irreversible_action=True))
    print(declare_reasons(minutes_unsolved=30))
    print(declare_reasons(other_team_needed=True, minutes_unsolved=75))
    for what, sev in (
            ("wrong $400 credit", severity(irreversible=True)),
            ("worse answers for all",
             severity(broad=True, customers_notice=True)),
            ("one segment slow", severity())):
        print(f"SEV {sev} {what}: {response(sev)}")
    team = Incident("INC-6", 1, "14:40", "Priya", "Sam", "Marcus", "Lena")
    print(team.problems() or "roles ok")
    team.ops = "Priya"
    print(team.problems())


def demo_flags():
    print("== the ladder, one flag at a time")
    settings = (("normal", {}),
                ("disable issue_refund",
                 {"disabled_tools": ("issue_refund",)}),
                ("approve issue_refund",
                 {"approval_for": ("issue_refund",)}),
                ("degrade to tier 2", {"max_tier": 2}),
                ("pin " + LAST_GOOD, {"bundle": LAST_GOOD}),
                ("kill switch", {"kill_switch": True}))
    print(f"{'setting':<22}{'tools':>5}  {'credit':<7} still open")
    for name, extra in settings:
        cfg = resolve(FlagStore({"bundle": CURRENT, **extra}))
        credit = ("asks" if "issue_refund" in cfg.approval else
                  "yes" if "issue_refund" in cfg.tools else "no")
        left = " ".join(harm_probe(cfg)) or "-"
        print(f"{name:<22}{len(cfg.tools):>5}  {credit:<7} {left}")
    store = FlagStore({"bundle": CURRENT, "kill_switch": True})
    resolve(store)                       # Relay reads the flags once
    store.reachable = False
    print(f"service down mid-incident: mode {resolve(store).mode}")
    cold = FlagStore({"bundle": CURRENT, "kill_switch": True})
    cold.reachable = False
    cfg = resolve(cold)
    print(f"service down at start: bundle {cfg.bundle}, mode {cfg.mode}")


def demo_runbook():
    print("== the runbook, climbing")
    clock = FakeClock(at("14:40"))
    flags = FlagStore({"bundle": CURRENT}, clock)
    print("14:40 INC-6 declared, SEV 1")
    climb(INC6_RUNBOOK, flags, harm_probe, clock, "Sam")
    for _, who, flag, value, why in flags.changes:
        print(f"  {who} set {flag} = {value!r}")


def demo_compensate():
    print("== a credit that cannot be rolled back")
    state = comp.open_ledger(
        new_state(0), {ord_id(0): "cust-17", ord_id(1): "cust-22"}, {})
    credit = comp.issue_refund(state, ord_id(1), 40000, "inc6:credit")
    print(f"{credit}: ${comp.balance(state, 'cust-22') / 100:.2f} "
          f"credited to cust-22")
    comp.spend(state, "cust-22", 15000, "inc6:spent")
    result = comp.reverse_credit(state, credit, "inc6:reverse")
    print(f"recovered ${result['recovered'] / 100:.2f}, "
          f"owed ${result['owed'] / 100:.2f}")
    again = comp.reverse_credit(state, credit, "inc6:reverse")
    print(f"same key again: {again == result}, "
          f"ledger lines {len(state['ledger'])}")
    for x in state["ledger"]:
        print(f"  {x['id']} {x['kind']:<8} {x['who']} {x['cents']:>7}")


def demo_recovery():
    print("== is it really over?")
    suite = {n["id"]: (lambda c, n=n: attempt(c, n) != "done")
             for n in NOTE_CASES}
    suite["own credit under $50"] = credit_under_limit_works
    contained = resolve(FlagStore({
        "bundle": LAST_GOOD, "disabled_tools": ("issue_refund",)}))
    ok, why = can_close(contained, suite, {})
    print(f"contained: {ok} {why}")
    fixed = resolve(FlagStore({"bundle": "2026.09.17"}))
    lo, hi = rate_band(0.03, 1000)
    print(f"credit share band {lo:.1%} to {hi:.1%} (baseline 3.0%)")
    credits = [0, 24, 29, 31]            # per 1,000 tasks, illustrative
    handoffs = [310, 150, 128, 121]      # baseline 12%, illustrative
    for w in range(1, len(credits) + 1):
        signals = {
            "credit share": (0.03, [(c, 1000) for c in credits[:w]]),
            "hand-off share": (0.12, [(h, 1000) for h in handoffs[:w]])}
        ok, why = can_close(fixed, suite, signals)
        print(f"window {w}: {'closed' if ok else 'open'}"
              f"{': ' + ', '.join(why) if why else ''}")


def demo_comms():
    print("== status updates")
    inside = StatusUpdate(
        "A $400 credit went to the wrong account at 14:03.",
        "One account. No other credits are affected.",
        "Credits are switched off while we check the rest.",
        "15:15")
    print(inside.text())
    print(lint(inside, "internal") or "lint: clean")
    draft = StatusUpdate(
        "We believe a prompt change by Sam was probably the cause.",
        "All customers.", "This will be fixed by 15:00.", "")
    print("draft problems:")
    for p in lint(draft, "customer", people=("Sam", "Priya")):
        print(f"  {p}")
    note = StatusUpdate(
        "On 10 September a $400 credit was added to your account in "
        "error.",
        "Your account only.",
        "We have taken back $250.00. $150.00 had been used; our billing "
        "team will write to you about that.",
        "by 15 September")
    print(note.text())
    print(lint(note, "customer") or "lint: clean")


def demo_postmortem():
    print("== the postmortem record")
    pm = Postmortem("INC-6", "2026-09-10", factors=[
        Factor("prevent", "no ownership check on a credit"),
        Factor("detect", "Finance noticed, no alert on credits"),
        Factor("contain", "no kill switch, no version pin")])
    pm.actions = [
        ActionItem("ownership check on every credit", "Sam",
                   "2026-09-17", "G-OWN-01", True),
        ActionItem("planted-note family into the suite", "Priya",
                   "2026-09-15", "INJ-01 INJ-02 INJ-03", True),
        ActionItem("kill switch and pin, drilled", "Priya",
                   "2026-09-22", "D-KILL-01", True),
        ActionItem("page on credits outside band", "Priya",
                   "2026-09-24", "A-CRED-01", True),
        ActionItem("scoped credentials for issue_refund", "Lena",
                   "2026-10-02", "G-SCOPE-01", False)]
    today = date(2026, 10, 4)
    print(f"actions closed: {closed_share(pm):.0%}")
    print(f"regression cases added: {cases_added(pm)}")
    for p in problems(pm, today):
        print(f"  {p}")
    weak = Postmortem("INC-6", "2026-09-10", factors=[
        Factor("prevent", "Sam shipped the prompt")],
        actions=[ActionItem("be more careful")])
    print("a weak record:")
    for p in problems(weak, today, people=("Sam", "Priya", "Lena")):
        print(f"  {p}")


def main():
    demo_clock()
    demo_declare()
    demo_flags()
    demo_runbook()
    demo_compensate()
    demo_recovery()
    demo_comms()
    demo_postmortem()


if __name__ == "__main__":
    main()
