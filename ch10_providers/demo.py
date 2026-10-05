"""Every Chapter 10 output.   python3 -m ch10_providers.demo"""
import random
import textwrap
from dataclasses import replace

from common.clock import FakeClock
from ch02_trust_outputs.refund import ToolError, validate_refund_args
from ch09_when_calls_fail.breaker import CircuitBreaker
from ch10_providers.adapters import STATUS_A, STATUS_B, adapt_a, adapt_b
from ch10_providers.adapters import adapted, retryable
from ch10_providers.cancel import (fresh_log, gateway, handle_chat,
                                   handle_leaky, record_outcome,
                                   refund_step)
from ch10_providers.catalog import (Request, make_catalog, rejections,
                                    NoEligibleProvider)
from ch10_providers.drill import (dry_run, model_a, model_b_tuned,
                                  model_b_untuned)
from ch10_providers.failover import (Hysteresis, SingleThreshold,
                                     plan_shift, with_warmup)
from ch10_providers.fakes import FULL, stream, to_a, to_b
from ch10_providers.ranking import Signals, rank, route, score
from ch10_providers.request_path import World, serve
from ch10_providers.scenarios import error_curve, rank_first
from ch10_providers.stream import (StreamResult, consume, lenient,
                                   recovery)
from ch10_providers.tiers import (ActionBlocked, choose_tier, guard_tool,
                                  notice)
from ch10_providers.vendor import allowed_downtime_minutes, chained
from ch10_providers.vtime import VirtualClock

MARIA = Request("eu", 30_000, True)
HEALTHY = {"Provider A": Signals(0.99, 1.2, 0.33),
           "Provider B": Signals(0.99, 1.5, 0.5),
           "Provider B small": Signals(0.99, 0.8, 1.0)}


def show_flood():
    print("== the detour floods the side street")
    normal = {"eu_chat": 20}
    demand = {"eu_chat": 20, "chat": 80}
    print(f"Provider B normally carries {sum(normal.values())} chats; "
          f"its limit is 40")
    print(f"naive failover: B gets {sum(demand.values())} chats, "
          f"{sum(demand.values()) // sum(normal.values())}x its load")
    placed, over = plan_shift(demand, 40)
    taken = ", ".join(f"{k} {v}" for k, v in placed.items() if v)
    print(f"controlled: B takes {taken} ({sum(placed.values())} of 40)")
    print(f"waiting or degrading: chat {over['chat']}")


def show_eligibility():
    print("== eligibility before optimisation")
    cat = make_catalog()
    big = replace(MARIA, tokens=150_000)
    for label, req in (("Maria (EU, 30,000 tokens, tools)", MARIA),
                       ("EU chat of 150,000 tokens, tools", big)):
        print(label)
        for p in cat:
            why = rejections(p, req)
            print(f"  {p.name:17} {'out: ' + ', '.join(why) if why else 'in'}")
    print(f"nobody in for the big chat: tier {choose_tier(cat, big)}")


def show_filter_first():
    print("== healthy beats eligible?")
    cat = make_catalog()
    pick = rank_first(cat, HEALTHY).name
    print(f"rank first, B has room:         {pick} (no tools)")
    cat[1].in_flight = cat[2].in_flight = 40
    pick = rank_first(cat, HEALTHY).name
    print(f"rank first, B and B small full: {pick} (leaves the EU)")
    try:
        route(cat, MARIA, HEALTHY)
    except NoEligibleProvider:
        print("filter first, same state:       none eligible: degrade")


def show_ranking():
    print("== ranking")
    cat = make_catalog()
    cat[0].in_flight, cat[1].in_flight = 80, 20
    chat = Request("global", 8_000, True)
    print("a normal day, a global chat that needs tools")
    for p in rank(cat, chat, HEALTHY):
        s = HEALTHY[p.name]
        print(f"  {p.name:11} success {s.success:.2f}  ttft {s.ttft}s  "
              f"free {s.headroom:.2f}  score {score(p, s):.2f}")
    print("  route:", route(cat, chat, HEALTHY).name)
    down = dict(HEALTHY, **{"Provider A": Signals(0.55, 4.0, 0.33, "open")})
    print("Provider A at 55% success, 4.0 s, breaker open")
    print("  route:", route(cat, chat, down).name)
    tight = dict(HEALTHY, **{"Provider A": Signals(0.99, 1.2, 0.10)})
    print(f"Provider A with 10% of its slots free: "
          f"{score(cat[0], tight['Provider A']):.2f}")


def show_hysteresis():
    print("== hysteresis on the schematic outage")
    for name, cls in (("single line at 12.5%", SingleThreshold),
                      ("hysteresis, leave 20 / back 5", Hysteresis)):
        clock = FakeClock()
        router = cls(clock)
        for t, error in error_curve():
            clock.sleep(t - clock.now())
            router.observe(error)
        flips = sum(1 for i, (t, s) in enumerate(router.log)
                    if s == 0.0 or router.log[i - 1][1] == 0.0)
        if cls is SingleThreshold:
            at = ", ".join(f"{t / 60:.1f}" for t, _ in router.log)
            print(f"{name}: {flips} route changes, at {at} min")
        else:
            print(f"{name}: {flips} route changes")
            steps = [f"{s:.0%} at {t / 60:.1f}" for t, s in router.log]
            print("  traffic to A: " + ", ".join(steps) + " min")


def show_warm_backup():
    print("== a warm backup")
    cat = make_catalog()
    ranked = rank(cat, Request("global", 8_000, True), HEALTHY)
    rng = random.Random(10)
    n = sum(with_warmup(ranked, rng).name == "Provider B"
            for _ in range(10_000))
    print(f"2% warm share, 10,000 requests: {n} went to Provider B")
    print("dry run, 5 refund cases through Chapter 2's checks")
    for label, model in (("Provider A, prompt A", model_a),
                         ("Provider B, prompt A", model_b_untuned),
                         ("Provider B, prompt B", model_b_tuned)):
        ok, total, first = dry_run(model)
        print(f"  {label}: {ok} of {total} valid"
              + (f" ({first})" if first else ""))


def show_tiers():
    print("== service tiers")
    rows = []
    cat = make_catalog()
    rows.append(("A down, B has room", cat, MARIA, True))
    cat = make_catalog()
    cat[1].in_flight = 40
    rows.append(("B at its limit", cat, MARIA, True))
    cat = make_catalog()
    cat[1].in_flight = cat[2].in_flight = 40
    rows.append(("B and B small full", cat, MARIA, True))
    rows.append(("... and the order database down", cat, MARIA, False))
    rows.append(("150,000-token EU chat", make_catalog(),
                 replace(MARIA, tokens=150_000), True))
    for label, c, req, db_up in rows:
        c[0].in_flight = c[0].limit        # Provider A is down for all
        print(f"{label:33} tier {choose_tier(c, req, db_up)}")
    blocked = []
    for tier in (1, 2):
        results = []
        for tool in ("lookup_order", "issue_refund"):
            try:
                guard_tool(tool, tier, blocked)
                results.append(f"{tool} ok")
            except ActionBlocked:
                results.append(f"{tool} blocked")
        print(f"tier {tier}: " + ", ".join(results))
    print(f"blocked actions logged: {len(blocked)}")
    for tier, hour in ((2, 14), (3, 14), (4, 22)):
        n = notice(tier, hour)
        print(textwrap.fill(n.text(), 70, subsequent_indent="    ",
                            initial_indent=f"tier {tier}, {hour}:00: "))


def show_adapters():
    print("== adapters")
    same = [adapt_a(to_a(e)) for e in FULL] == \
        [adapt_b(to_b(e)) for e in FULL] == FULL
    print("the same events from both dialects:", same)
    for label, status in (("Provider A 'overloaded'", STATUS_A["overloaded"]),
                          ("Provider B 'rate_limited'",
                           STATUS_B["rate_limited"])):
        print(f"{label} -> {status}, retryable: {retryable(status)}")


def show_streams():
    print("== a stream dies at 70%")
    clock, shown = VirtualClock(), []
    res = clock.run(consume(stream(FULL, clock, cut_after=7),
                            shown.append, clock))
    print(f"events delivered: 7 of {len(FULL)}; status: {res.status} "
          f"({res.why})")
    print("customer saw:", " |".join(shown))
    print("tool call run:", res.tool_call)
    print("draft ends:", "..." + res.partial_tool[-32:])
    risky = lenient(res.partial_tool)
    checked = validate_refund_args(risky, "cust-22")
    verdict = checked.code if isinstance(checked, ToolError) else "accepted"
    print(f"a lenient parser makes {risky['amount_cents']} cents; "
          f"Chapter 2's checks: {verdict}")
    clock = VirtualClock()
    res = clock.run(consume(stream(FULL, clock, stall_after=4),
                            lambda s: None, clock))
    print(f"a stalled stream: {res.status} ({res.why}) "
          f"after {clock.now():.1f} s")
    clock = VirtualClock()
    res = clock.run(consume(stream(FULL, clock), lambda s: None, clock))
    print(f"a whole stream: {res.status}, stop {res.stop}, "
          f"amount_cents {res.tool_call['amount_cents']}")


def show_recovery():
    print("== resume, restart, or neither")
    cut = StreamResult("incomplete", ["One."], partial_tool="{...")
    text = StreamResult("incomplete", ["One."])
    none = StreamResult("incomplete")
    cases = (("tool call cut", cut, {}),
             ("text cut after a sentence", text, {}),
             ("nothing shown yet", none, {}),
             ("refund paid, reply cut", text, {"effect_done": True}),
             ("refund sent, no answer", cut, {"outcome_unknown": True}))
    for label, res, facts in cases:
        action, why = recovery(res, **facts)
        print(f"{label:26} {action}: {why}")


def show_cancellation():
    print("== the tab closes at 3.05 s")
    for name, handler, at in (("leaky", handle_leaky, 3.05),
                              ("owned", handle_chat, 3.05)):
        clock, log = VirtualClock(), fresh_log()
        clock.run(gateway(handler, log, clock, at))
        after = log["tokens"] - log["tokens_at_cancel"]
        ran = log["closed_at"] - log["cancelled_at"]
        print(f"{name}: {log['tokens_at_cancel']} tokens before, {after} "
              f"after ({ran:.0f} s more), status {log['status']}")
    print(f"  owned: retry ran {log['retry_ran']}, "
          f"tool started {log['tool_started']}")
    clock, log = VirtualClock(), fresh_log()
    clock.run(gateway(refund_step, log, clock, 0.2))
    print(f"cancelled mid-payment at 0.2 s: refund {log['refund']}, "
          f"status {log['status']}")
    clock = FakeClock()
    breaker = CircuitBreaker(clock=clock)
    for _ in range(10):
        record_outcome(breaker, "cancelled")
    print(f"10 cancelled calls: breaker {breaker.state}")
    for _ in range(5):
        record_outcome(breaker, "failed")
    print(f"then 5 failed calls: breaker {breaker.state}")


def show_request():
    print("== one request through the incident")
    clock = VirtualClock()
    world = World(clock)
    lines = []
    done = clock.run(serve(world, MARIA, "cust-22", "conv-1",
                           lines.append))
    for line in lines:
        print(" ", line)
    print(f"payouts: {world.payments.calls}; refund {done['refund_id']}")
    print(f"calls by provider: {dict(world.calls)}; "
          f"residency violations: {world.violations}")


def show_vendor():
    print("== reading an SLA")
    print(f"99.9% over 30 days allows "
          f"{allowed_downtime_minutes(0.999, 30):.1f} minutes down")
    print(f"99.5% over 28 days allows "
          f"{allowed_downtime_minutes(0.995, 28):.1f} minutes down")
    print(f"two 99.9% providers, perfect failover: "
          f"{chained(0.999, 0.999):.6f}")


def main():
    show_flood()
    show_eligibility()
    show_filter_first()
    show_ranking()
    show_hysteresis()
    show_warm_backup()
    show_tiers()
    show_adapters()
    show_streams()
    show_recovery()
    show_cancellation()
    show_request()
    show_vendor()


if __name__ == "__main__":
    main()
