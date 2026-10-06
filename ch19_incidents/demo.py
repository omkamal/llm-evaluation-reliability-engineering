"""Every Chapter 19 output.   python3 -m ch19_incidents.demo"""
import json
from datetime import date

from ch06_agents.sandbox import new_state, ord_id
from ch11_traces.tracer import IdGenerator, Tracer
from ch13_drift.bands import check_rate, rate_band
from common.clock import FakeClock
from ch19_incidents import compensate as comp
from ch19_incidents.comms import StatusUpdate, lint
from ch19_incidents.declare import (Incident, declare_reasons, response,
                                    severity)
from ch19_incidents.detect import credits_without_approver
from ch19_incidents.flags import LAST_GOOD, NORMAL, FlagStore, resolve
from ch19_incidents.postmortem import (ActionItem, Factor, Postmortem,
                                       cases_added, closed_share,
                                       problems)
from ch19_incidents.recovery import can_close
from ch19_incidents.runbook import INC6_RUNBOOK, climb
from ch19_incidents.standin import (NOTE_CASES, credit_under_limit_works,
                                    harm_probe, attempt, reworded)
from ch19_incidents.timeline import (Scribe, at, clock_text, durations,
                                     merge, render, trace_rows)

# Relay's task layer: about 840,000 tasks in 28 days, some 21 a minute
TASKS_PER_MINUTE = 840_000 / (28 * 24 * 60)


def inc6_replay():
    """The machine side of INC-6: one trace, as Chapter 11 records it."""
    clock = FakeClock(at("14:02"))
    tracer = Tracer(clock, IdGenerator(seed=6))
    with tracer.span("invoke_agent Planner", "agent", attrs={
            "gen_ai.conversation.id": "c-7731"}):
        clock.sleep(60)
        # the stranger's order from Chapter 17's telling of the same message
        args = {"order_id": "ORD-004831", "amount_cents": 40000,
                "reason": "other"}
        with tracer.span("execute_tool issue_refund", "tool", attrs={
                "gen_ai.tool.name": "issue_refund", "relay.tool.tier": 2,
                "enduser.id": "cust-17",          # the sender's session
                "relay.tool.args": json.dumps(args, sort_keys=True)}):
            clock.sleep(2)
    return clock, tracer.finished


def inc6_clock():
    """INC-6 on the one clock: a trace for the machine side, the scribe's
    log for the people side. The people lines are what the incident
    log would say; times are the incident's (RELAY-FACTS)."""
    clock, spans = inc6_replay()
    scribe = Scribe(clock)
    rows = trace_rows(spans)
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
    # the detect action, tested on the replay before it is written down
    n = round(TASKS_PER_MINUTE * 5)
    usual = round(0.03 * n)              # credits in 3% of tasks
    print(f"credit band, {n} tasks in 5 min, {usual + 1} credits: "
          f"{check_rate(0.03, usual + 1, n)}")
    for t, text in credits_without_approver(inc6_replay()[1]):
        print(f"credit rule: pages at {clock_text(t)}, {text}")


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
    # a small team doubles up: Marcus writes updates and keeps the log
    team = Incident("INC-6", 1, "14:40", "Priya", "Sam", "Marcus",
                    "Marcus")
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
        cfg = resolve(FlagStore({**NORMAL, **extra}))
        credit = ("asks" if "issue_refund" in cfg.approval else
                  "yes" if "issue_refund" in cfg.tools else "no")
        left = " ".join(harm_probe(cfg)) or "-"
        print(f"{name:<22}{len(cfg.tools):>5}  {credit:<7} {left}")
    pinned = resolve(FlagStore({**NORMAL, "bundle": LAST_GOOD}))
    left = harm_probe(pinned, [reworded(c) for c in NOTE_CASES])
    print(f"pin {LAST_GOOD}, notes reworded: {' '.join(left)}")
    store = FlagStore({**NORMAL, "kill_switch": True})
    resolve(store)                       # Relay reads the flags once
    store.reachable = False
    print(f"service down mid-incident: mode {resolve(store).mode}")
    cold = FlagStore({**NORMAL, "kill_switch": True})
    cold.reachable = False               # a restart, nothing saved
    cfg = resolve(cold)
    print(f"service down at a cold start: bundle {cfg.bundle}, "
          f"mode {cfg.mode}")


def demo_runbook():
    print("== the runbook, climbing")
    clock = FakeClock(at("14:40"))
    flags = FlagStore(NORMAL, clock)
    print("14:40 INC-6 declared, SEV 1")
    climb(INC6_RUNBOOK, flags, harm_probe, clock, "Sam")
    for _, who, flag, value, why in flags.changes:
        print(f"  {who} set {flag} = {value!r}")


def demo_compensate():
    print("== a credit that cannot be rolled back")
    state = comp.open_ledger(
        new_state(0), {ord_id(0): "cust-17", ord_id(1): "cust-22"},
        {"cust-22": 3000})               # $30 of the customer's own
    credit = comp.issue_refund(state, ord_id(1), 40000, "inc6:credit")
    print(f"{credit}: $400.00 credited to cust-22, who held $30.00")
    comp.spend(state, "cust-22", 15000, "inc6:spent")
    try:
        comp.reverse_credit(state, credit, "inc6:reverse")
    except comp.NeedsFinance:
        print("no approver: nothing posted")
    result = comp.reverse_credit(state, credit, "inc6:reverse",
                                 approved_by="Finance")
    print(f"recovered ${result['recovered'] / 100:.2f}, "
          f"owed ${result['owed'] / 100:.2f}, cust-22 keeps "
          f"${comp.balance(state, 'cust-22') / 100:.2f}")
    again = comp.reverse_credit(state, credit, "inc6:reverse",
                                approved_by="Finance")
    print(f"same key again: {again == result}, "
          f"ledger lines {len(state['ledger'])}")
    for x in state["ledger"]:
        print(f"  {x['id']} {x['kind']:<8} {x['who']} {x['cents']:>7}")


def demo_recovery():
    print("== is it really over?")
    suite = {n["id"]: (lambda c, n=n: attempt(c, n) != "done")
             for n in NOTE_CASES}
    suite["own credit under $50"] = credit_under_limit_works
    contained = resolve(FlagStore({**NORMAL, "bundle": LAST_GOOD,
                                   "disabled_tools": ("issue_refund",)}))
    ok, why = can_close(contained, suite, {})
    print(f"contained: {ok} {why}")
    fixed = resolve(FlagStore({**NORMAL, "bundle": "2026.09.17"}))
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
        "One account so far; other credits are being checked.",
        "Credits are switched off while we check.",
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
        "We have taken back the unused $250.00 of it.",
        "by 15 September")
    print(note.text())
    print(lint(note, "customer") or "lint: clean")


def demo_postmortem():
    print("== the postmortem record")
    pm = Postmortem("INC-6", "2026-09-10", factors=[
        Factor("prevent", "no ownership check on a credit"),
        Factor("detect", "Finance noticed, no alert on credits"),
        Factor("contain", "no kill switch, no version pin, and the "
               "planted note stayed on the order")])
    pm.actions = [
        ActionItem("ownership check on every credit", "Sam",
                   "2026-09-17", "G-OWN-01", True),
        ActionItem("planted-note family into the suite", "Priya",
                   "2026-09-15", "INJ-01 INJ-02 INJ-03", True),
        ActionItem("kill switch and pin, drilled", "Priya",
                   "2026-09-22", "D-KILL-01", True),
        ActionItem("page on any credit that skipped a person", "Priya",
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
