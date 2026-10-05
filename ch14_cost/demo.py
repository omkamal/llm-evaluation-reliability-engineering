"""Every Chapter 14 output.   python3 -m ch14_cost.demo"""
from datetime import date

from common.clock import FakeClock
from ch01_anatomy.call import count_tokens
from ch08_rag.corpus import DOCS, OLD_FREE_SHIPPING
from ch08_rag.lifecycle import fingerprint
from ch10_providers.catalog import (NoEligibleProvider, Request,
                                    make_catalog)
from ch11_traces.context import (MUST_KEEP, careful_summarize,
                                 fields_lost, long_session, summarize)
from ch14_cost.capacity import (best_commitment, day_cost, in_flight,
                                load_test)
from ch14_cost.cascade import (cascade, frontier_only, make_cases, router,
                               small_only, summary)
from ch14_cost.dashboard import PANELS, TARGET, check_spec
from ch14_cost.economics import (CALLS_PER_TASK, LENGTH_MIX, NEW_PER_TURN,
                                 PREFIX, cumulative_input,
                                 conversation_usd, eaters,
                                 long_session_shares, resolved_cost,
                                 task_usd)
from ch14_cost.faq import ASKED, CACHED
from ch14_cost.finops import (Record, forecast_miss, monthly_bill,
                              showback, status)
from ch14_cost.latency import (critical_path, first_words, parallel,
                               schedule, sequential, waterfall)
from ch14_cost.levers import (batch_usd, compress, lane, reply_usd,
                              saved_per_call, tokens)
from ch14_cost.prices import PRICES, call_usd
from ch14_cost.prompt_cache import (PrefixCache, break_even_uses,
                                    equivalent_tokens)
from ch14_cost.prove import compare
from ch14_cost.routing import route
from ch14_cost.semantic_cache import SemanticCache


def demo_growth():
    print("== the cost of remembering")
    a, b = cumulative_input(5), cumulative_input(20)
    print(f"5 turns: {a:,} input tokens, ${conversation_usd(5):.3f}")
    print(f"20 turns: {b:,} input tokens, ${conversation_usd(20):.3f}")
    ratio = conversation_usd(20) / conversation_usd(5)
    print(f"{b / a:.1f}x the input tokens, {ratio:.1f}x the cost")
    share, tokens_share = long_session_shares()
    print(f"conversations over 12 turns: {share:.0%}; "
          f"their share of input tokens: {tokens_share:.0%}")


def demo_task():
    print("== one task, then per resolved task")
    usd = task_usd()
    print(f"{CALLS_PER_TASK} calls on the frontier tier: ${usd:.4f}")
    print(f"80 of 100 resolved: ${resolved_cost(usd, 0.8):.4f} "
          "per resolved task")
    print(f"the SLO line: ${TARGET}")


def demo_eaters():
    print("== hidden token eaters")
    base, extra = eaters()
    print(f"a task costs ${base:.4f}; each eater adds:")
    for name, usd in extra.items():
        print(f"  {name:<46}${usd:.4f}  +{usd / base:.0%}")


def demo_forecast():
    print("== a forecast")
    per_task = CALLS_PER_TASK * call_usd("frontier", PREFIX, 250)
    bill = monthly_bill(900_000)
    print(f"900,000 tasks x {CALLS_PER_TASK} calls x "
          f"${per_task / CALLS_PER_TASK:.4f} = ${bill:,.0f} "
          "(invoice: $42,000)")
    predicted, miss = forecast_miss(42_000, 0.15, 85_000)
    print(f"traffic alone: ${predicted:,.0f}; the invoice: $85,000, "
          f"${miss:,.0f} more")
    print(f"per task: ${42_000 / 900_000:.4f} before, "
          f"${85_000 / 1_035_000:.4f} after")
    cut = 1 - monthly_bill(1, 0.6) / monthly_bill(1)
    print(f"60% of calls on the small tier: -{cut:.0%}, "
          f"about ${85_000 * (1 - cut):,.0f}")


def demo_showback():
    print("== showback by tenant")
    records = []
    for tenant, tasks, turns, ok in (("consumer app", 700, 4, 0.94),
                                     ("sellers", 250, 8, 0.90),
                                     ("enterprise pilot", 50, 20, 0.80)):
        usd = conversation_usd(turns)
        records += [Record("support", tenant, usd, i < tasks * ok)
                    for i in range(tasks)]
    total = sum(r.usd for r in records)
    print("tenant            tasks   spend  share  per resolved")
    for tenant, (n, spend, per) in showback(records, "tenant").items():
        print(f"{tenant:<16}{n:>7}  ${spend:>5.2f}  {spend / total:>4.0%}"
              f"   ${per:.4f}")
    for team, spent, budget in (("support chat", 15_000, 30_000),
                                ("nightly jobs", 4_000, 12_000)):
        print(f"{team}: ${spent:,} on day 12 of a ${budget:,} cost "
              f"budget: {status(spent, 12, budget)}")


def demo_policies():
    print("== cascade, router, and the others")
    cases = make_cases()
    base, _ = frontier_only(cases)
    casc, stepped, _ = cascade(cases)
    lenient, step2, _ = cascade(cases, true_negative=0.60)
    route_, to_big = router(cases)
    n = len(cases)
    rows = [("frontier only", base, 1.0), ("small only", small_only(cases), 0.0),
            ("cascade", casc, stepped / n),
            ("lenient cascade", lenient, step2 / n),
            ("router", route_, to_big / n)]
    print("policy            $/task  resolved  $/resolved  p95 s  to frontier")
    for name, tasks, share in rows:
        usd, ok, per, p95 = summary(tasks)
        print(f"{name:<16}{usd:>8.4f}{ok:>9.1%}{per:>12.4f}"
              f"{p95:>7.1f}{share:>9.0%}")
    print("== paired against frontier only, margin 2 points")
    for name, tasks in (("cascade", casc), ("lenient cascade", lenient),
                        ("router", route_)):
        v = compare(base, tasks)
        print(f"{name + ':':<17}saves {v.saving:.0%}, resolved "
              f"{v.change * 100:+.1f} points "
              f"[{v.low * 100:+.1f}, {v.high * 100:+.1f}]: "
              f"{'ship' if v.ship else 'blocked'}")
    capped, step3, held = cascade(cases, cap_usd=1.00)
    print(f"$1.00 cap on step-ups: {step3} stepped up, {held} held, "
          f"resolved {summary(capped)[1]:.1%}")


def demo_routing():
    print("== route by price, inside the rules")
    catalog = make_catalog()
    asks = [("summary, global customer", Request("global", 8_000, False), ()),
            ("lookup_order, global", Request("global", 8_000, True), ()),
            ("lookup_order, EU customer", Request("eu", 8_000, True), ()),
            ("issue_refund planned", Request("global", 8_000, True),
             ("issue_refund",)),
            ("150,000-token EU chat", Request("eu", 150_000, True), ())]
    for name, req, planned in asks:
        try:
            print(f"{name:<27}-> {route(catalog, req, planned)}")
        except NoEligibleProvider:
            print(f"{name:<27}-> none eligible: degrade")


def demo_prompt_cache():
    print("== prompt cache, 20 turns")

    def run(gap=40.0, stamp=False, cached=True):
        clock = FakeClock()
        cache = PrefixCache(clock)
        worth = hit = total = 0
        for turn in range(1, 21):
            head = [(f"time {turn}", 20)] if stamp else []
            blocks = head + [("system, tools, policy", PREFIX)]
            blocks += [(f"turn {i}", NEW_PER_TURN) for i in range(1, turn)]
            c, w, f = cache.send(blocks) if cached else (0, 0, sum(
                n for _, n in blocks))
            worth += equivalent_tokens(c, w, f)
            hit, total = hit + c, total + c + w + f
            clock.sleep(gap)
        return worth, hit / total

    rows = [("no cache", run(cached=False)),
            ("stable prefix first", run()),
            ("timestamp at the top", run(stamp=True)),
            ("400 s between turns", run(gap=400.0))]
    print("                      token-equivalents   cost  hit rate")
    for name, (worth, rate) in rows:
        usd = worth * PRICES["frontier"].inp / 1_000_000
        print(f"{name:<22}{worth:>12,.0f}{f'${usd:.3f}':>10}{rate:>9.0%}")
    print(f"writing a prefix pays from use number {break_even_uses()}")


def fresh_cache(threshold, guard):
    live = {d.id: fingerprint(d) for d in DOCS}
    cache = SemanticCache(lambda doc: live[doc], threshold, guard)
    for _, question, answer in CACHED:
        cache.store("standard", question, answer, {})
    return cache


def demo_semantic():
    print("== semantic cache: threshold sweep")
    right_answer = {intent: answer for intent, _, answer in CACHED}
    same = sum(i in right_answer for i, _ in ASKED)
    print(f"{same} paraphrases, {len(ASKED) - same} look-alikes with "
          "other answers")
    print("threshold  paraphrases hit  wrong answers  share of hits wrong")
    for threshold in (0.5, 0.7, 0.8, 0.9):
        cache = fresh_cache(threshold, guard=False)
        right = wrong = 0
        for intent, question in ASKED:
            hit = cache.lookup("standard", question)
            if hit:
                ok = hit.answer == right_answer.get(intent)
                right, wrong = right + ok, wrong + (not ok)
        print(f"{threshold:>9}{right:>12} of {same}{wrong:>11} of "
              f"{len(ASKED) - same}{wrong / (right + wrong):>15.0%}")


def demo_semantic_rules():
    print("== semantic cache: the rules")
    for guard in (False, True):
        cache = fresh_cache(0.7, guard)
        cache.store("standard", "Is shipping free over $60?",
                    "Yes, over $60.", {})
        hit = cache.lookup("standard", "Is shipping free over $40?")
        label = "on " if guard else "off"
        print(f"slot guard {label}: {hit.answer if hit else 'miss'}")
    cache = fresh_cache(0.7, True)
    ask = "How many days can I return an unused item?"
    for tenant in ("standard", "enterprise"):
        hit = cache.lookup(tenant, ask)
        print(f"{tenant} tenant asks: {hit.answer if hit else 'miss'}")
    print("order-status answer stored:",
          cache.store("standard", "Where is my order?", "Tomorrow.", {},
                      tools=("lookup_order",)))
    live = {d.id: fingerprint(d) for d in DOCS}
    cache = SemanticCache(lambda doc: live[doc], 0.8)
    cache.store("standard", "Is shipping free over a set amount?",
                "Orders over $40 ship free.",
                {"free-shipping": fingerprint(OLD_FREE_SHIPPING)})
    hit = cache.lookup("standard", "Is shipping free over a set amount?")
    print(f"cached 3 Sep, asked 4 Oct, source changed: "
          f"{'hit' if hit else 'miss'}, {cache.dropped} entry dropped")


def demo_levers():
    print("== batch, compress, say less")
    jobs = 5_000
    usd = jobs * call_usd("small", 8_000, 400)
    print(f"lane for a 0.01 h deadline: {lane(0.01)}; for 24 h: {lane(24)}")
    print(f"{jobs:,} nightly summaries: ${usd:.2f} now, "
          f"${batch_usd(usd):.2f} as a batch")
    turns = long_session()
    for name, summarizer in (("lossy summary:", summarize),
                             ("careful summary:", careful_summarize)):
        new = compress(turns, 7_900, summarizer)
        lost = fields_lost(MUST_KEEP, new) or "none"
        print(f"{name:<17}{tokens(turns):,} -> {tokens(new):,} tokens, "
              f"lost: {lost[0] if lost != 'none' else lost}")
    print(f"each later call saves ${saved_per_call(31_800, 7_900):.4f} "
          "of input")
    essay = ("Thanks for reaching out! I have checked your order and I "
             "am sorry for the delay. The refund will reach you within "
             "five business days of us receiving the item.")
    for name, text in (("essay", essay), ("json", '{"route": "refund"}')):
        print(f"{name} reply: {count_tokens(text)} tokens, "
              f"${reply_usd(text) * 100_000:.2f} per 100,000 replies")


def demo_latency():
    print("== latency")
    for name, steps in (("sequential", sequential()),
                        ("parallel", parallel())):
        total = max(end for _, end in schedule(steps).values())
        path = " > ".join(critical_path(steps))
        print(f"{name:<11}{total:.1f} s  critical path: {path}")
    print(f"parallel, streamed: first words at {first_words(parallel())} s")
    for row in waterfall(parallel()):
        print(row)


def demo_capacity():
    print("== capacity")
    peak = in_flight(1_000, 6.0)
    print(f"1,000 chats a minute x 6 s = {peak:.0f} calls in flight")
    print(f"limit 120: headroom {(120 - peak) / 120:.0%}; "
          f"limit 40: short by {peak - 40:.0f}")
    print("load of the limit  per minute  p95 latency  missed deadline")
    for share in (0.5, 0.9, 1.0, 1.05, 1.2):
        per_minute = round(share * 40 / 2.0 * 60)
        p95, missed = load_test(40, 2.0, per_minute)
        print(f"{share:>14.0%}{per_minute:>12,}{p95:>9.1f} s{missed:>14.1%}")
    profile = [120] * 6 + [320] * 3 + [540] * 8 + [720] * 4 + [300] * 3
    on_demand = day_cost(profile, 0, 0.6)
    best = best_commitment(profile, 0.6)
    print("commit (k tokens/min)  share of the on-demand day")
    for name, level in (("none", 0), ("the average", round(
            sum(profile) / 24)), ("the peak", max(profile)),
                        ("best", best)):
        share = day_cost(profile, level, 0.6) / on_demand
        print(f"{name:<12}{level:>5}{share:>20.0%}")


def demo_dashboard():
    print("== the dashboard spec")
    print(f"{len(PANELS)} panels, target ${TARGET}, "
          f"problems: {check_spec() or 'none'}")


def main():
    for demo in (demo_growth, demo_task, demo_eaters, demo_forecast,
                 demo_showback, demo_policies, demo_routing,
                 demo_prompt_cache, demo_semantic, demo_semantic_rules,
                 demo_levers, demo_latency, demo_capacity, demo_dashboard):
        demo()


if __name__ == "__main__":
    main()
