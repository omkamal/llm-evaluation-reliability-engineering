"""Chapter 14: every worked example in the text is asserted here."""
import pytest

from common.clock import FakeClock
from ch08_rag.corpus import DOCS, OLD_FREE_SHIPPING
from ch08_rag.lifecycle import fingerprint
from ch10_providers.catalog import (NoEligibleProvider, Request,
                                    make_catalog)
from ch11_traces.context import (MUST_KEEP, careful_summarize,
                                 fields_lost, long_session, summarize)
from ch12_slos.sheet import SHEET
from ch14_cost import capacity, dashboard, finops, latency, levers
from ch14_cost.cascade import (cascade, check_passes, frontier_only,
                               make_cases, router, small_only, summary)
from ch14_cost.economics import (LENGTH_MIX, NEW_PER_TURN, PREFIX,
                                 cumulative_input, conversation_usd,
                                 eaters, long_session_shares,
                                 resolved_cost, task_usd, turn_input)
from ch14_cost.faq import ASKED, CACHED
from ch14_cost.prices import PRICES, call_usd
from ch14_cost.prompt_cache import (PrefixCache, break_even_uses,
                                    equivalent_tokens)
from ch14_cost.prove import compare
from ch14_cost.routing import route
from ch14_cost.semantic_cache import (SemanticCache, cosine, embed,
                                      slots)

# ---- prices and token economics ---------------------------------------


def test_every_small_price_is_below_the_frontier_price():
    small, big = PRICES["small"], PRICES["frontier"]
    assert small.inp < big.inp and small.out < big.out


def test_output_costs_four_times_input():
    for price in PRICES.values():
        assert price.out == pytest.approx(4 * price.inp)


def test_cached_reads_are_cheap_and_writes_are_dear():
    plain = call_usd("frontier", 3000, 0)
    assert call_usd("frontier", 0, 0, cached_in=3000) == pytest.approx(
        plain * 0.1)
    assert call_usd("frontier", 0, 0, written=3000) == pytest.approx(
        plain * 1.25)


def test_reasoning_tokens_bill_like_output():
    hidden = call_usd("frontier", 0, 0, hidden=1500)
    assert hidden == pytest.approx(1500 * 8 / 1_000_000)
    assert hidden == call_usd("frontier", 0, 1500)


def test_the_chart_numbers_five_and_twenty_turns():
    assert cumulative_input(5) == 21_000
    assert cumulative_input(20) == 174_000
    assert turn_input(1) == PREFIX
    assert turn_input(2) == PREFIX + NEW_PER_TURN


def test_cumulative_input_grows_with_the_square():
    # n*P + a*n*(n-1)/2: the second term is quadratic
    for n in (3, 10, 20):
        assert cumulative_input(n) == PREFIX * n + NEW_PER_TURN * n * (
            n - 1) // 2
    assert cumulative_input(40) / cumulative_input(20) > 3.3


def test_four_times_the_turns_is_eight_times_the_tokens_and_7_5_the_cost():
    assert cumulative_input(20) / cumulative_input(5) == pytest.approx(
        8.29, abs=0.01)
    assert conversation_usd(5) == pytest.approx(0.052)
    assert conversation_usd(20) == pytest.approx(0.388)
    assert conversation_usd(20) / conversation_usd(5) == pytest.approx(
        7.46, abs=0.01)


def test_the_invented_mix_reproduces_the_incident_shape():
    share, tokens = long_session_shares()
    assert round(share, 2) == 0.08 and round(tokens, 2) == 0.46
    assert sum(w for w, _, _ in LENGTH_MIX) == pytest.approx(1.0)


def test_cost_per_resolved_task_example():
    assert task_usd() == pytest.approx(0.048)
    assert resolved_cost(task_usd(), 0.8) == pytest.approx(0.06)
    # failing more makes a task dearer per resolved task, not per task
    assert resolved_cost(task_usd(), 0.5) > resolved_cost(task_usd(), 0.8)


def test_hidden_eaters_add_up_as_the_text_says():
    base, extra = eaters()
    shares = sorted(round(v / base, 2) for v in extra.values())
    assert shares == [0.17, 0.30, 0.50, 0.62]


# ---- FinOps -----------------------------------------------------------


def test_forecast_from_tokens_is_close_to_the_invoice():
    bill = finops.monthly_bill(900_000)
    assert bill == pytest.approx(43_200)
    assert abs(bill / 42_000 - 1) < 0.03


def test_traffic_alone_misses_the_invoice_by_36_700():
    predicted, miss = finops.forecast_miss(42_000, 0.15, 85_000)
    assert predicted == pytest.approx(48_300)
    assert miss == pytest.approx(36_700)
    assert 85_000 / 1_035_000 == pytest.approx(0.0821, abs=0.0001)


def test_moving_sixty_percent_of_calls_to_small_cuts_48_percent():
    cut = 1 - finops.monthly_bill(1, 0.6) / finops.monthly_bill(1)
    assert round(cut, 2) == 0.48
    assert 85_000 * (1 - cut) == pytest.approx(44_200)


def test_month_end_projection_and_status():
    assert finops.projection(15_000, 12) == pytest.approx(37_500)
    assert finops.status(15_000, 12, 30_000) == "over by 25%"
    assert finops.status(4_000, 12, 12_000) == "on course"


def test_showback_groups_by_tenant_and_counts_resolved_only():
    rows = [finops.Record("t", "a", 1.0, True),
            finops.Record("t", "a", 1.0, False),
            finops.Record("t", "b", 2.0, True)]
    out = finops.showback(rows, "tenant")
    assert out["a"] == (2, 2.0, 2.0)       # 2 dollars over 1 resolved
    assert out["b"] == (1, 2.0, 2.0)


# ---- cascade, router and the guardrails -------------------------------


@pytest.fixture(scope="module")
def cases():
    return make_cases()


def test_cases_are_deterministic_and_about_18_percent_hard(cases):
    assert cases == make_cases()
    assert 0.15 < sum(c.hard for c in cases) / len(cases) < 0.21


def test_the_check_has_the_error_rates_it_claims():
    many = make_cases(20_000, seed=5)
    bad = [c for c in many if not c.small_ok]
    good = [c for c in many if c.small_ok]
    caught = sum(not check_passes(c, 0.95) for c in bad) / len(bad)
    alarms = sum(not check_passes(c, 0.95) for c in good) / len(good)
    assert caught == pytest.approx(0.95, abs=0.01)
    assert alarms == pytest.approx(0.03, abs=0.005)


def test_the_cascade_steps_up_19_percent_and_saves_61(cases):
    base, _ = frontier_only(cases)
    tasks, stepped, held = cascade(cases)
    usd, ok, per, p95 = summary(tasks)
    assert round(stepped / len(cases), 2) == 0.19 and held == 0
    assert round(usd, 4) == 0.0031
    assert round(1 - usd / summary(base)[0], 2) == 0.61
    assert p95 == pytest.approx(3.3)         # a step-up pays twice in time
    assert summary(base)[3] == pytest.approx(2.4)


def test_small_only_is_cheapest_and_fails_about_one_in_five(cases):
    usd, ok, per, _ = summary(small_only(cases))
    base = summary(frontier_only(cases)[0])
    assert usd < base[0] and per < base[2]
    assert base[1] - ok > 0.12


def test_a_lenient_check_steps_up_less_and_loses_quality(cases):
    strict = cascade(cases, true_negative=0.95)
    lenient = cascade(cases, true_negative=0.60)
    assert lenient[1] < strict[1]
    assert summary(lenient[0])[1] < summary(strict[0])[1] - 0.03


def test_the_router_is_faster_but_never_checks(cases):
    tasks, to_big = router(cases)
    assert summary(tasks)[3] < summary(cascade(cases)[0])[3]
    assert 0.18 < to_big / len(cases) < 0.24


def test_the_cap_holds_step_up_spend_and_flags_the_rest(cases):
    tasks, stepped, held = cascade(cases, cap_usd=1.00)
    assert held > 0 and stepped * 0.008 <= 1.00
    assert stepped + held == cascade(cases)[1]


def test_paired_comparison_ships_the_cascade_and_blocks_the_lenient(cases):
    base, _ = frontier_only(cases)
    good = compare(base, cascade(cases)[0])
    bad = compare(base, cascade(cases, true_negative=0.60)[0])
    assert good.ship and round(good.saving, 2) == 0.61
    assert good.low > -0.02 and round(good.change, 3) == -0.009
    assert not bad.ship and bad.high < -0.03
    with pytest.raises(ValueError):
        compare(base, base[:10])


def test_routing_filters_first_then_ranks_by_price():
    cat = make_catalog()
    assert route(cat, Request("global", 8_000, False)) == "Provider B small"
    assert route(cat, Request("global", 8_000, True)) == "Provider A"
    assert route(cat, Request("eu", 8_000, True)) == "Provider B"
    assert route(cat, Request("eu", 8_000, False)) == "Provider B small"


def test_an_irreversible_step_never_goes_to_the_small_tier():
    cat = make_catalog()
    req = Request("global", 8_000, False)       # B small would be cheapest
    assert route(cat, req) == "Provider B small"
    assert route(cat, req, ("issue_refund",)) == "Provider A"
    assert route(cat, req, ("lookup_order",)) == "Provider B small"


def test_an_eu_request_never_reaches_provider_a_whatever_the_price():
    cat = make_catalog()
    for tools in (True, False):
        assert route(cat, Request("eu", 8_000, tools),
                     ("issue_refund",)) == "Provider B"
    with pytest.raises(NoEligibleProvider):
        route(cat, Request("eu", 150_000, True))


# ---- prompt cache -----------------------------------------------------


def conversation(turns, gap=40.0, stamp=False, cache=None):
    clock = FakeClock()
    cache = cache or PrefixCache(clock)
    worth = hit = total = 0
    for turn in range(1, turns + 1):
        blocks = [(f"time {turn}", 20)] if stamp else []
        blocks += [("system", PREFIX)]
        blocks += [(f"turn {i}", NEW_PER_TURN) for i in range(1, turn)]
        c, w, f = cache.send(blocks)
        worth += equivalent_tokens(c, w, f)
        hit, total = hit + c, total + c + w + f
        cache.clock.sleep(gap)
    return worth, hit / total


def test_a_stable_prefix_cuts_the_input_to_a_fifth():
    worth, rate = conversation(20)
    assert worth == pytest.approx(33_960)
    assert worth / cumulative_input(20) == pytest.approx(0.195, abs=0.001)
    assert round(rate, 2) == 0.92


def test_a_timestamp_at_the_top_breaks_every_hit_and_costs_more():
    worth, rate = conversation(20, stamp=True)
    assert rate == 0.0 and worth > cumulative_input(20)


def test_a_gap_longer_than_the_ttl_misses_but_use_keeps_it_alive():
    assert conversation(20, gap=400.0)[1] == 0.0
    assert conversation(20, gap=200.0)[1] > 0.9   # each use restarts it


def test_a_short_prompt_is_not_cached_and_pays_the_normal_price():
    cache = PrefixCache(FakeClock())
    assert cache.send([("tiny", 600)]) == (0, 0, 600)
    assert cache.send([("tiny", 600)]) == (0, 0, 600)


def test_writing_a_prefix_pays_from_the_second_use():
    assert break_even_uses() == 2


# ---- semantic cache ---------------------------------------------------


def make_cache(threshold, guard=True):
    live = {d.id: fingerprint(d) for d in DOCS}
    cache = SemanticCache(lambda doc: live[doc], threshold, guard)
    for _, question, answer in CACHED:
        cache.store("standard", question, answer, {})
    return cache


def sweep(threshold):
    right = {i: a for i, _, a in CACHED}
    cache = make_cache(threshold, guard=False)
    hits = wrong = 0
    for intent, question in ASKED:
        hit = cache.lookup("standard", question)
        if hit:
            hits += 1
            wrong += hit.answer != right.get(intent)
    return hits, wrong


def test_cosine_of_identical_questions_is_one():
    q = "How many days do I have to return an unused item?"
    assert cosine(embed(q), embed(q)) == pytest.approx(1.0)


def test_hits_fall_as_the_threshold_rises_and_wrong_hits_fall_to_zero():
    results = [sweep(t) for t in (0.5, 0.7, 0.8, 0.9)]
    assert [h for h, _ in results] == sorted(
        (h for h, _ in results), reverse=True)
    assert results[0] == (28, 10) and results[-1] == (6, 0)
    assert all(w > 0 for _, w in results[:3])   # no threshold is free


def test_a_slot_guard_stops_forty_dollars_hitting_sixty():
    for guard, expected in ((False, "Yes, over $60."), (True, None)):
        cache = make_cache(0.7, guard)
        cache.store("standard", "Is shipping free over $60?",
                    "Yes, over $60.", {})
        hit = cache.lookup("standard", "Is shipping free over $40?")
        assert (hit.answer if hit else None) == expected
    assert slots("Is it free over $40?") == frozenset({"$40"})
    assert "not" in slots("Can I not pay?")


def test_a_hit_never_crosses_tenants():
    cache = make_cache(0.7)
    ask = "How many days can I return an unused item?"
    assert cache.lookup("standard", ask).answer.startswith("Within 14")
    assert cache.lookup("enterprise", ask) is None
    cache.store("enterprise", "How many days to return an unused item?",
                "30 days.", {})
    assert cache.lookup("enterprise", ask).answer == "30 days."
    assert cache.lookup("standard", ask).answer.startswith("Within 14")


def test_an_answer_built_from_a_customers_data_is_never_stored():
    cache = make_cache(0.7)
    n = len(cache.entries)
    assert cache.store("standard", "Where is my order?", "Tomorrow.", {},
                       tools=("lookup_order",)) is False
    assert len(cache.entries) == n
    assert cache.store("standard", "What are the support hours?",
                       "8:00 to 20:00.", {}, tools=("lookup_policy",))


def test_a_changed_source_expires_the_entry_even_when_it_matches():
    live = {d.id: fingerprint(d) for d in DOCS}
    cache = SemanticCache(lambda doc: live[doc], 0.8)
    q = "Is shipping free over a set amount?"
    cache.store("standard", q, "Orders over $40 ship free.",
                {"free-shipping": fingerprint(OLD_FREE_SHIPPING)})
    assert cache.lookup("standard", q) is None and cache.dropped == 1
    assert cache.entries == []
    cache.store("standard", q, "Orders over $60 ship free.",
                {"free-shipping": live["free-shipping"]})
    assert cache.lookup("standard", q).answer.endswith("ship free.")
    assert cache.dropped == 1


# ---- batch, compress, output ------------------------------------------


def test_lane_and_batch_discount():
    assert levers.lane(0.01) == "interactive" and levers.lane(24) == "batch"
    assert levers.batch_usd(19.20) == pytest.approx(9.60)
    assert 5_000 * call_usd("small", 8_000, 400) == pytest.approx(19.20)


def test_a_lossy_summary_drops_the_address_and_a_careful_one_keeps_it():
    turns = long_session()
    lossy = levers.compress(turns, 7_900, summarize)
    careful = levers.compress(turns, 7_900, careful_summarize)
    assert levers.tokens(turns) == 31_800
    assert levers.tokens(lossy) == levers.tokens(careful) == 7_900
    assert fields_lost(MUST_KEEP, lossy) == ["delivery_address"]
    assert fields_lost(MUST_KEEP, careful) == []
    assert levers.saved_per_call(31_800, 7_900) == pytest.approx(0.0478)


def test_the_reply_is_the_dear_side():
    essay = ("Thanks for reaching out! I have checked your order and I "
             "am sorry for the delay. The refund will reach you within "
             "five business days of us receiving the item.")
    assert levers.reply_usd(essay) * 100_000 == pytest.approx(26.40)
    assert levers.reply_usd('{"route": "refund"}') * 100_000 == (
        pytest.approx(7.20))


# ---- latency ----------------------------------------------------------


def test_the_waterfall_matches_the_figure():
    seq, par = latency.schedule(latency.sequential()), latency.schedule(
        latency.parallel())
    assert seq["answer"][1] == pytest.approx(5.3)
    assert par["answer"][1] == pytest.approx(4.5)
    assert latency.first_words(latency.parallel()) == pytest.approx(2.5)


def test_only_the_critical_path_is_worth_speeding_up():
    assert latency.critical_path(latency.parallel()) == [
        "plan", "search", "answer"]
    faster_track = [latency.Step("plan", 1.2),
                    latency.Step("track", 0.1, ("plan",)),
                    latency.Step("search", 0.9, ("plan",)),
                    latency.Step("answer", 2.4, ("track", "search"))]
    assert latency.schedule(faster_track)["answer"][1] == pytest.approx(4.5)
    faster_search = [latency.Step("plan", 1.2),
                     latency.Step("track", 0.8, ("plan",)),
                     latency.Step("search", 0.5, ("plan",)),
                     latency.Step("answer", 2.4, ("track", "search"))]
    assert latency.schedule(faster_search)["answer"][1] == pytest.approx(
        4.4)


# ---- capacity ---------------------------------------------------------


def test_littles_law_gives_100_calls_in_flight_at_the_peak():
    assert capacity.in_flight(1_000, 6.0) == pytest.approx(100)
    assert capacity.in_flight(21, 6.0) == pytest.approx(2.1)


def test_latency_is_flat_until_the_limit_and_then_falls_off_a_cliff():
    p50, _ = capacity.load_test(40, 2.0, 600)
    p90, miss90 = capacity.load_test(40, 2.0, 1_080)
    over, miss_over = capacity.load_test(40, 2.0, 1_260)
    assert p90 < 1.2 * p50 and miss90 == 0.0
    assert over > 3 * p90 and miss_over > 0.0
    assert capacity.load_test(40, 2.0, 1_260) == (over, miss_over)


def test_commit_to_the_level_demand_reaches_often_enough():
    profile = [120] * 6 + [320] * 3 + [540] * 8 + [720] * 4 + [300] * 3
    b = 0.6
    best = capacity.best_commitment(profile, b)
    assert best == 320
    day = capacity.day_cost
    assert day(profile, best, b) < day(profile, 0, b)
    assert day(profile, 720, b) > day(profile, 0, b)     # peak: too much
    # the marginal unit is used at least b of the hours up to `best`
    hours_at_least = sum(d >= best for d in profile) / len(profile)
    assert hours_at_least >= b
    assert sum(d >= 540 for d in profile) / len(profile) < b


# ---- dashboard --------------------------------------------------------


def test_the_dashboard_spec_is_complete_and_uses_the_slo_target():
    assert dashboard.check_spec() == []
    assert dashboard.TARGET == next(
        s.target for s in SHEET if s.name == "cost per resolved task")


def test_a_cost_panel_without_a_quality_panel_is_flagged():
    cost_only = tuple(p for p in dashboard.PANELS
                      if "judge" not in p.metric)
    assert any("no panel for judge pass rate" in x
               for x in dashboard.check_spec(cost_only))
    odd = dashboard.Panel("x", ("a",), "email", "Sam")
    assert any("unknown route" in x for x in dashboard.check_spec((odd,)))


def test_the_demo_prints_the_numbers_the_chapter_quotes(capsys):
    from ch14_cost import demo
    demo.main()
    out = capsys.readouterr().out
    for line in ("8.3x the input tokens, 7.5x the cost",
                 "cascade           0.0031    94.6%      0.0033    3.3"
                 "      19%",
                 "stable prefix first         33,960    $0.068      92%",
                 "parallel   4.5 s  critical path: plan > search > answer"):
        assert line in out


# ---- the answers printed in the chapter -------------------------------


def test_try_it_one_tighten_the_check(cases=None):
    cases = make_cases()
    base, _ = frontier_only(cases)
    rows = []
    for t in (0.80, 0.90, 0.95, 0.99):
        tasks, stepped, _ = cascade(cases, true_negative=t)
        v = compare(base, tasks)
        rows.append((round(stepped / len(cases), 2), round(v.saving, 2),
                     round(v.low * 100, 1), v.ship))
    assert rows == [(0.16, 0.63, -4.1, False), (0.18, 0.62, -2.6, False),
                    (0.19, 0.61, -1.5, True), (0.20, 0.60, -0.5, True)]


def test_try_it_two_move_the_gap():
    assert conversation(20, gap=60.0)[1] == pytest.approx(0.917, abs=0.001)
    assert conversation(20, gap=299.0)[1] == pytest.approx(0.917, abs=0.001)
    assert conversation(20, gap=300.0)[1] == 0.0


def test_try_it_three_a_slower_day():
    assert capacity.in_flight(1_000, 9.0) == pytest.approx(150)
    assert 120 / 9 * 60 == pytest.approx(800)


def test_check_questions_one_and_two():
    assert turn_input(10) == 8_400 and cumulative_input(10) == 57_000
    assert 48 / 1_000 == pytest.approx(0.048)
    assert 48 / 900 == pytest.approx(0.0533, abs=0.0001) and 48 / 900 < 0.06


def test_a_cascade_step_up_pays_twice_in_time(cases):
    assert 0.9 + 2.4 == pytest.approx(3.3)
    assert summary(cascade(cases)[0])[3] > summary(
        frontier_only(cases)[0])[3]


def test_check_questions_three_and_four(cases):
    assert conversation(20, stamp=True)[0] == pytest.approx(218_000)
    base, _ = frontier_only(cases)
    tasks, stepped, _ = cascade(cases, true_negative=0.60)
    v = compare(base, tasks)
    assert round(stepped / len(cases), 2) == 0.13
    assert (round(v.change * 100, 1), round(v.low * 100, 1),
            round(v.high * 100, 1)) == (-5.4, -6.9, -4.0)
    assert round(summary(small_only(cases))[1], 3) == 0.823
