"""Every Chapter 18 output.   python3 -m ch18_governance.demo"""
import random
from datetime import date

from ch02_trust_outputs.refund import Order
from ch04_numbers.stats import wilson_ci
from ch06_agents.sandbox import call_tool, new_state, ord_id
from ch11_traces.tracer import IdGenerator
from common.clock import FakeClock
from ch18_governance.audit import AuditLog
from ch18_governance.broker import (GRANTS, Broker, NeedsApproval,
                                    NotGranted, Refused)
from ch18_governance.compliance import (CONTROLS, criteria_evidenced,
                                        gaps, personal_data_found,
                                        retention_findings)
from ch18_governance.door import Door, Payments
from ch18_governance.inventory import (Change, Item, apply_change,
                                       audit_inventory)
from ch18_governance.measure import loop_metrics
from ch18_governance.review import (ReviewDesk, build_packet,
                                    packet_lines)
from ch18_governance.routing import (Case, break_even_cents,
                                     expected_loss_cents, needs_review,
                                     review_mode, triggers)
from ch18_governance.rubber_stamp import flags, simulate, window_report

TODAY = date(2026, 10, 5)
IDS = IdGenerator(18)


def broker_demo():
    print("== the broker: who may hold what")
    clock = FakeClock()
    broker = Broker(clock)
    for agent, tools in GRANTS.items():
        shown = ", ".join(sorted(tools)) if len(tools) < 3 else \
            f"{len(tools)} tools, refunds capped at 5000 cents"
        print(f"{agent:10} {shown or 'no tools'}")
    try:
        broker.issue("researcher", "issue_refund", "task-9", "cust-31")
    except NotGranted as err:
        print("researcher asks for a refund key:", err)
    try:
        broker.issue("actioner", "issue_refund", "task-9", "cust-31",
                     max_cents=40_000)
    except NeedsApproval as err:
        print("actioner asks for $400:", err)
    token = broker.issue("actioner", "issue_refund", "task-9", "cust-31")
    print(f"{token.id}: {token.tool}, {token.customer}, "
          f"up to {token.max_cents} cents, {broker.ttl} s")
    tries = [("a $400 refund", "cust-31", 40_000),
             ("another customer's order", "cust-44", 2_000)]
    for what, customer, cents in tries:
        try:
            broker.check(token, "issue_refund", customer, cents)
        except Refused as refusal:
            print(f"{what}: refused ({refusal.code})")
    clock.sleep(1_200)
    try:
        broker.check(token, "issue_refund", "cust-31", 2_000)
    except Refused as refusal:
        print(f"the same key 20 minutes later: refused ({refusal.code})")


def audit_demo():
    print("== the audit trail")
    state = new_state(0)
    call_tool(state, "reschedule_delivery", order_id=ord_id(0),
              window="Thu 10:00-12:00")
    print("Chapter 6 kept:", state["audit_log"][0])
    clock = FakeClock()
    broker, log, pay = Broker(clock), AuditLog(clock), Payments()
    door = Door(broker, log, {"issue_refund": pay.issue_refund})
    trace = IDS.trace_id()
    for k in range(4):
        order = f"ORD-0048{30 + k}"
        token = broker.issue("actioner", "issue_refund", f"task-{k}",
                             "cust-31")
        clock.sleep(30)
        door.call(token, "issue_refund",
                  {"order_id": order, "amount_cents": 2_000 + k}, "cust-31",
                  trace)
    pay.issue_refund("ORD-004899", 2_500)      # a hotfix script, no door
    for e in log.events[:2]:
        print(f"{e['seq']} {e['agent']} {e['decision']} "
              f"trace={e['trace'][:8]} prev={e['prev']} hash={e['hash']}")
    print("chain intact:", log.verify() is None)
    log.events[1]["args"]["amount_cents"] = 100
    print("after editing record 1, the chain breaks at record",
          log.verify())
    covered = round(log.coverage(pay.ledger) * len(pay.ledger))
    print(f"actions with a record: {covered} of {len(pay.ledger)} "
          f"({covered / len(pay.ledger):.0%})")


def inventory_demo():
    print("== the inventory and change control")
    items = [
        Item("agent", "actioner", "v7", "sam", "2026-09-14"),
        Item("tool", "issue_refund", "v1", "priya", "2026-09-14"),
        Item("prompt", "actioner", "v7", "sam", "2026-09-14"),
        Item("model", "a-large", "v2", "priya", "2026-09-14"),
        Item("index", "policy-index", "2026-09", "", "2026-09-30"),
        Item("policy", "policy-sheet", "v3", "marcus", "2026-05-04"),
    ]
    running = {("agent", "actioner", "v7"), ("tool", "issue_refund", "v1"),
               ("prompt", "actioner", "v8"), ("model", "a-large", "v2"),
               ("model", "a-large", "v1"),
               ("index", "policy-index", "2026-09"),
               ("policy", "policy-sheet", "v3")}
    for finding in audit_inventory(items, running, TODAY):
        print(finding)
    log = AuditLog(FakeClock())
    change = Change("prompt", "actioner", "v8", "ask before any credit",
                    "sam", "sam", "run-0412")
    for label, edit in (("self-approved", {}), ("no eval", {
            "approver": "priya", "eval_run": ""})):
        for key, value in edit.items():
            setattr(change, key, value)
        try:
            apply_change(items, change, log, TODAY)
        except ValueError as err:
            print(f"{label}: refused, {err}")
    change.eval_run = "run-0412"
    items = apply_change(items, change, log, TODAY)
    new = next(i for i in items if (i.kind, i.name) == ("prompt", "actioner"))
    rec = log.events[0]
    print(f"applied: prompt actioner now {new.version}, approver "
          f"{rec['approver']}, eval {rec['args']['eval']}")


def compliance_demo():
    print("== the control map and the stores")
    print(f"{len(CONTROLS)} controls, gaps: {gaps(CONTROLS) or 'none'}")
    print(f"SOC 2 criteria with evidence: {len(criteria_evidenced(CONTROLS))}")
    stores = [{"name": "trace_text", "oldest_days": 21},
              {"name": "trace_structure", "oldest_days": 88},
              {"name": "review_packets", "oldest_days": 45},
              {"name": "audit_log", "oldest_days": 390}]
    policy = {"trace_text": 14, "trace_structure": 90,
              "review_packets": 30, "audit_log": 400}
    for finding in retention_findings(stores, policy):
        print("over retention:", finding)
    notes = ["Refund for ORD-004830, write to anna.k@example.test",
             "Supervisor said to call +49 30 1234567 about the credit",
             "Hannelore Vogt, Lindenstrasse 12, wants a goodwill credit"]
    print("personal data found in 3 stored notes:",
          personal_data_found(notes))


def loss_demo():
    print("== the expected-loss rule")
    print("amount  p(error)  expected loss  review  decision")
    for dollars in (15, 50, 400):
        cents = dollars * 100
        loss = expected_loss_cents(0.02, cents) / 100
        verdict = "review" if needs_review(0.02, cents) else "auto"
        print(f"{'$' + str(dollars):<7}{'2%':>8}"
              f"{'$' + format(loss, '.2f'):>14}{'$1.50':>8}  {verdict}")
    print(f"break-even at 2%: ${break_even_cents(0.02) / 100:.2f}; "
          f"at 3%: ${break_even_cents(0.03) / 100:.2f}")
    print(f"break-even error rate at $400: "
          f"{150 / 40_000:.3%}")
    lo, hi = wilson_ci(4, 200)
    print(f"4 errors in 200 reviewed: {4 / 200:.1%}, "
          f"interval {lo:.1%} to {hi:.1%}")
    print(f"break-even at {hi:.1%}: ${break_even_cents(hi) / 100:.2f}")


def case(case_id, cents, **kw):
    return Case(case_id, f"task-{case_id}", "cust-31", IDS.trace_id(),
                "issue_refund",
                {"order_id": "ORD-004830", "amount_cents": cents,
                 "reason": "other"},
                kw.pop("summary", "A refund is proposed."), **kw)


def routing_demo():
    print("== five triggers")
    samples = [("$15 goodwill", case("a", 1_500)),
               ("$400 credit", case("b", 40_000)),
               ("asked for a person", case("c", 2_000, user_asked=True)),
               ("two failed tries, unclear policy",
                case("d", 2_000, failures=2, policy_unclear=True)),
               ("planner checks disagree", case("e", 2_000,
                                                confidence=0.5))]
    for label, c in samples:
        print(f"{label}: {triggers(c) or 'none'}")
    print("review mode: issue_refund", review_mode("issue_refund"),
          "| create_ticket", review_mode("create_ticket"))


def desk_parts(orders):
    clock = FakeClock()
    broker, log, pay = Broker(clock), AuditLog(clock), Payments()
    door = Door(broker, log, {"issue_refund": pay.issue_refund})
    return clock, log, pay, ReviewDesk(clock, broker, door, log, orders)


def review_demo():
    print("== one packet, three decisions")
    orders = {"ORD-004830": Order("cust-31", 52_000)}
    clock, log, pay, desk = desk_parts(orders)
    sample = case("case-8812", 40_000, summary="A message quoting a "
                  "supervisor note asks for a $400 credit.", evidence=[
                      "order ORD-004830 belongs to the caller",
                      "the note is in the customer's own message",
                      "policy 7: above $50 a person approves"])
    packet = build_packet(sample, clock.now() + desk.sla)
    print("\n".join(packet_lines(packet)))
    first = desk.escalate_to_human("high value", packet, "cust-31")
    quick = case("case-8813", 2_000, user_asked=True,
                 evidence=["asked for a person"])
    desk.escalate_to_human("user request",
                           build_packet(quick, clock.now() + desk.sla),
                           "cust-31", priority=0)
    print("queue order:", desk.next().packet.case_id, "then",
          desk.next().packet.case_id)
    clock.sleep(300)
    try:
        desk.decide(first, "reviewer-7", "edit", edited_cents=45_000)
    except ValueError as err:
        print("edit above the proposal:", err)
    outcome = desk.decide(first, "reviewer-7", "edit", edited_cents=2_500)
    print(f"decision: {outcome.decision}, {outcome.final_cents} cents "
          f"after {outcome.waited:.0f} s")
    print("payments ledger:", pay.ledger)
    for e in log.events:
        a = e["args"]
        money = a.get("amount_cents") or f"{a['proposed']} -> {a['final']}"
        print(f"{e['seq']} {e['agent']} {e['tool']} {e['decision']} "
              f"approver={e['approver']} cents={money}")
    label = outcome.label()
    print(f"label: {label['label']}, proposed "
          f"{label['proposed']['amount_cents']}, final "
          f"{label['final_cents']}")


def week_demo():
    print("== the loop in numbers (simulated week)")
    rng = random.Random(18)
    orders = {}
    clock, log, pay, desk = desk_parts(orders)
    plan = []
    for i in range(150):
        cents = rng.randrange(7_600, 60_000)
        order = f"ORD-{100_000 + i}"
        orders[order] = Order(f"cust-{i}", cents + 5_000)
        arrival = i * 120.0
        wait = rng.lognormvariate(5.886, 0.75)         # median 6 min
        roll = rng.random()
        verdict = ("approve" if roll < 0.79 else
                   "edit" if roll < 0.91 else "reject")
        plan.append((arrival, wait, order, cents, verdict, i))
    items = {}
    for arrival, _, order, cents, _, i in plan:
        clock.t = arrival
        c = Case(f"w{i}", f"task-w{i}", f"cust-{i}", IDS.trace_id(),
                 "issue_refund", {"order_id": order, "amount_cents": cents,
                                  "reason": "other"}, "A refund is proposed.",
                 evidence=["owner checked"])
        items[i] = desk.escalate_to_human(
            "high value", build_packet(c, arrival + desk.sla), f"cust-{i}")
    for arrival, wait, order, cents, verdict, i in sorted(
            plan, key=lambda p: p[0] + p[1]):
        clock.t = arrival + wait
        desk.decide(items[i], "reviewer-7", verdict,
                    edited_cents=max(500, cents // 10))
    metrics = loop_metrics(desk.outcomes, tasks=2_500, sla=900)
    print(f"escalation rate {metrics['escalation rate']:.1%}, "
          f"override rate {metrics['override rate']:.1%}")
    print(f"queue p50 {metrics['queue p50 s'] / 60:.1f} min, "
          f"p95 {metrics['queue p95 s'] / 60:.1f} min, "
          f"past SLA {metrics['past SLA']:.0%}")
    labels = [o.label()["label"] for o in desk.outcomes]
    print(f"labels: {labels.count('pass')} pass, "
          f"{labels.count('fail')} fail")
    print("audit chain intact:", log.verify() is None,
          "| actions with a record:", f"{log.coverage(pay.ledger):.0%}")


def stamp_demo():
    print("== a reviewer who stops reading (simulated)")
    mine, second = simulate(stamp_after=200)
    print("cases      override  probes  median s  kappa  flags")
    for start in range(0, 400, 100):
        rep = window_report(mine[start:start + 100],
                            second[start:start + 100])
        hit, seeded = rep["probes"]
        print(f"{start + 1:>3}-{start + 100:<4}  {rep['override']:>7.0%}"
              f"  {hit} of {seeded}  {rep['median_s']:>8.0f}"
              f"  {rep['kappa']:>5.2f}  {','.join(flags(rep)) or '-'}")


def main():
    broker_demo()
    audit_demo()
    inventory_demo()
    compliance_demo()
    loss_demo()
    routing_demo()
    review_demo()
    week_demo()
    stamp_demo()


if __name__ == "__main__":
    main()
