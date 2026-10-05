"""Chapter 10 as tests. `pytest -q ch10_providers`"""
import asyncio
import io
import random
from contextlib import redirect_stdout
from dataclasses import replace

import pytest

from common.clock import FakeClock
from ch02_trust_outputs.refund import RefundArgs, validate_refund_args
from ch09_when_calls_fail.breaker import CircuitBreaker
from ch10_providers import demo
from ch10_providers.adapters import (STATUS_A, STATUS_B, adapt_a, adapt_b,
                                     retryable)
from ch10_providers.cancel import (fresh_log, gateway, handle_chat,
                                   handle_leaky, record_outcome,
                                   refund_step)
from ch10_providers.catalog import (NoEligibleProvider, Request, eligible,
                                    make_catalog, rejections)
from ch10_providers.drill import (dry_run, model_a, model_b_tuned,
                                  model_b_untuned)
from ch10_providers.failover import (Hysteresis, SingleThreshold,
                                     plan_shift, with_warmup)
from ch10_providers.fakes import FULL, GOOD_CALL, stream, to_a, to_b
from ch10_providers.health import HealthWindow
from ch10_providers.ranking import (W_HEALTH, W_SPEED, W_THRIFT, Signals,
                                    health, rank, route, score)
from ch10_providers.request_path import World, serve
from ch10_providers.scenarios import error_curve, rank_first
from ch10_providers.stream import (StreamResult, consume, lenient,
                                   recovery)
from ch10_providers.tiers import (ActionBlocked, MODEL_TOOLS, choose_tier,
                                  guard_tool, notice, support_open)
from ch10_providers.vendor import allowed_downtime_minutes, chained
from ch10_providers.vtime import VirtualClock

MARIA = Request("eu", 30_000, True)
HEALTHY = {"Provider A": Signals(0.99, 1.2, 0.33),
           "Provider B": Signals(0.99, 1.5, 0.5),
           "Provider B small": Signals(0.99, 0.8, 1.0)}


# ---- eligibility: filter first -------------------------------------

def test_only_provider_b_may_serve_maria():
    cat = make_catalog()
    assert [p.name for p in eligible(cat, MARIA)] == ["Provider B"]
    assert rejections(cat[0], MARIA) == ["residency"]
    assert rejections(cat[2], MARIA) == ["tools"]


def test_a_huge_eu_chat_has_no_eligible_provider_and_no_rule_bends():
    cat, big = make_catalog(), replace(MARIA, tokens=150_000)
    assert eligible(cat, big) == []
    with pytest.raises(NoEligibleProvider):
        route(cat, big, HEALTHY)
    assert choose_tier(cat, big) == 3


def test_capability_and_policy_filters():
    cat = make_catalog()
    cat[1].cleared = False                       # B's prompt never passed
    assert "capability" in rejections(cat[1], MARIA)
    blocked = replace(MARIA, region="global", blocked=frozenset({"Provider A"}))
    assert "policy" in rejections(cat[0], blocked)


def test_ranking_never_returns_a_provider_outside_the_region():
    rng = random.Random(3)                       # a property test, seeded
    for _ in range(300):
        cat = make_catalog()
        for p in cat:
            p.in_flight = rng.randrange(0, p.limit + 1)
        sig = {p.name: Signals(rng.random(), rng.uniform(0.2, 6),
                               p.free_slots / p.limit,
                               rng.choice(["closed", "open"]))
               for p in cat}
        req = Request("eu", rng.choice([5_000, 30_000, 150_000]),
                      rng.random() < 0.5)
        for p in rank(cat, req, sig):
            assert "eu" in p.regions


def test_ranking_first_breaks_residency_and_tools():
    cat = make_catalog()
    assert rank_first(cat, HEALTHY).name == "Provider B small"
    cat[1].in_flight = cat[2].in_flight = 40
    assert "eu" not in rank_first(cat, HEALTHY).regions   # the mistake
    with pytest.raises(NoEligibleProvider):
        route(cat, MARIA, HEALTHY)


# ---- ranking and health --------------------------------------------

def test_weights_match_figure_10_3():
    assert (W_HEALTH, W_SPEED, W_THRIFT) == (0.6, 0.3, 0.1)
    assert W_HEALTH + W_SPEED + W_THRIFT == pytest.approx(1.0)


def test_scores_on_a_normal_day_and_with_low_headroom():
    cat = make_catalog()
    assert round(score(cat[0], HEALTHY["Provider A"]), 3) == 0.892
    assert round(score(cat[1], HEALTHY["Provider B"]), 3) == 0.864
    low = Signals(0.99, 1.2, 0.10)
    assert health(low) == pytest.approx(0.495)
    assert round(score(cat[0], low), 2) == 0.59


def test_a_normal_day_prefers_a_and_an_outage_prefers_b():
    cat = make_catalog()
    chat = Request("global", 8_000, True)
    assert route(cat, chat, HEALTHY).name == "Provider A"
    down = dict(HEALTHY, **{"Provider A": Signals(0.55, 4.0, 0.33, "open")})
    assert route(cat, chat, down).name == "Provider B"


def test_tie_break_is_cheaper_then_name_and_ignores_input_order():
    a = replace(make_catalog()[1], name="Provider C", cost=8.0)
    b = replace(make_catalog()[1], name="Provider B", cost=8.0)
    cheap = replace(make_catalog()[1], name="Provider Z", cost=7.0)
    sig = {n: Signals(0.99, 1.5, 0.5) for n in ("Provider B",
                                                "Provider C", "Provider Z")}
    req = Request("global", 1_000, True)
    first = [p.name for p in rank([a, b, cheap], req, sig)]
    for order in ([cheap, b, a], [b, a, cheap], [a, cheap, b]):
        assert [p.name for p in rank(order, req, sig)] == first
    # equal to two decimals counts as a tie: cheaper first, then the name
    assert first == ["Provider Z", "Provider B", "Provider C"]


def test_full_or_open_providers_are_not_candidates():
    cat = make_catalog()
    cat[1].in_flight = 40
    assert rank(cat, MARIA, HEALTHY) == []
    cat[1].in_flight = 0
    open_ = dict(HEALTHY, **{"Provider B": Signals(0.99, 1.5, 0.5, "open")})
    assert rank(cat, MARIA, open_) == []


def test_health_window_forgets_and_stays_neutral_without_data():
    clock = FakeClock()
    h = HealthWindow(clock)
    assert h.success() == 0.5                    # no data is not health
    for i in range(40):
        h.record(i % 10 != 0, 1.0 + i / 100)
    assert h.success() == pytest.approx(0.9)
    assert h.ttft_p95() == pytest.approx(1.38)
    clock.sleep(301)                             # everything is stale
    assert h.success() == 0.5 and h.ttft_p95() == 5.0


# ---- failover without flooding -------------------------------------

def run_router(cls, **kw):
    clock = FakeClock()
    router = cls(clock, **kw)
    for t, error in error_curve():
        clock.sleep(t - clock.now())
        router.observe(error)
    return router


def test_hysteresis_matches_figure_10_4_to_the_decimal():
    log = run_router(Hysteresis).log
    assert [(round(t / 60, 1), s) for t, s in log] == [
        (7.0, 0.0), (31.3, 0.1), (35.3, 0.5), (39.3, 1.0)]


def test_a_single_line_flaps_on_the_same_outage():
    log = run_router(SingleThreshold).log
    assert [round(t / 60, 1) for t, _ in log] == [6.2, 18.7, 19.2, 22.4]


def test_one_wobble_resets_the_calm_period():
    clock = FakeClock()
    h = Hysteresis(clock)
    h.observe(25)                                # leave
    clock.sleep(200)
    h.observe(3)                                 # calm starts
    clock.sleep(250)
    h.observe(8)                                 # a wobble erases 250 s
    clock.sleep(10)
    h.observe(3)                                 # calm starts again
    clock.sleep(299)
    assert h.observe(3) == 0.0                   # 299 s: not yet
    clock.sleep(1)
    assert h.observe(3) == 0.1                   # 300 s unbroken: ramp


def test_a_bad_minute_during_the_ramp_sends_traffic_away_again():
    clock = FakeClock()
    h = Hysteresis(clock)
    h.observe(30)
    h.observe(1)
    clock.sleep(300)
    assert h.observe(1) == 0.1
    assert h.observe(20) == 0.0


def test_capacity_check_places_eu_chats_first_and_the_rest_wait():
    placed, over = plan_shift({"eu_chat": 20, "chat": 80}, 40)
    assert placed["eu_chat"] == 20 and placed["chat"] == 20
    assert over == {"eu_chat": 0, "chat": 60, "background": 0}
    assert 100 / 20 == 5                         # the 5x of the incident


def test_eu_demand_alone_can_exceed_the_limit_and_background_goes_first():
    placed, over = plan_shift({"eu_chat": 50, "chat": 10,
                               "background": 5}, 40)
    assert placed == {"eu_chat": 40, "chat": 0, "background": 0}
    assert over["eu_chat"] == 10 and over["background"] == 5


def test_a_warm_share_reaches_the_runner_up_and_nobody_else():
    cat = make_catalog()
    ranked = rank(cat, Request("global", 8_000, True), HEALTHY)
    rng = random.Random(10)
    picks = [with_warmup(ranked, rng).name for _ in range(10_000)]
    assert 150 <= picks.count("Provider B") <= 250
    assert set(picks) <= {p.name for p in ranked}
    eu = rank(cat, MARIA, HEALTHY)
    assert {with_warmup(eu, rng).name for _ in range(500)} == {"Provider B"}
    assert round(1_000_000 / 28 * 0.02) == 714   # chats a day at 2%


def test_the_untuned_backup_fails_the_dry_run_and_the_tuned_one_passes():
    assert dry_run(model_a)[:2] == (5, 5)
    ok, total, first = dry_run(model_b_untuned)
    assert (ok, total, first) == (0, 5, "schema: invalid_arguments")
    assert dry_run(model_b_tuned)[:2] == (5, 5)


# ---- service tiers ------------------------------------------------

def a_down_catalog():
    cat = make_catalog()
    cat[0].in_flight = cat[0].limit              # Provider A is down
    return cat


def test_tier_ladder_for_marias_request():
    cat = a_down_catalog()
    assert choose_tier(cat, MARIA) == 1
    cat[1].in_flight = 40
    assert choose_tier(cat, MARIA) == 2
    cat[2].in_flight = 40
    assert choose_tier(cat, MARIA) == 3
    assert choose_tier(cat, MARIA, db_up=False) == 4


def test_a_free_provider_outside_the_region_does_not_lift_the_tier():
    cat = make_catalog()                         # A has plenty of room
    cat[1].in_flight = cat[2].in_flight = 40
    assert choose_tier(cat, MARIA) == 3          # not 1: A may not serve EU
    assert choose_tier(cat, replace(MARIA, region="global")) == 1


def test_degraded_tiers_block_irreversible_actions():
    log = []
    for tool in MODEL_TOOLS[1]:
        guard_tool(tool, 1, log)
    assert log == []
    for tier in (2, 3, 4):
        for tool in ("issue_refund", "reschedule_delivery",
                     "reset_password", "escalate_incident"):
            with pytest.raises(ActionBlocked):
                guard_tool(tool, tier, log)
    guard_tool("lookup_order", 2, log)
    assert len(log) == 12


def test_notices_are_short_honest_and_have_a_next_step():
    for tier in (2, 3, 4):
        n = notice(tier, 14)
        assert n.what and n.works and n.next
        assert len(n.text().split()) <= 35
        assert "sorry" not in n.text().lower()
    assert "now" in notice(4, 14).next and "8:00 tomorrow" in notice(4, 22).next
    assert support_open(8) and not support_open(20) and not support_open(7)


# ---- adapters ------------------------------------------------------

def test_two_dialects_become_one_format():
    assert [adapt_a(to_a(e)) for e in FULL] == FULL
    assert [adapt_b(to_b(e)) for e in FULL] == FULL


def test_both_providers_errors_land_in_chapter_9_classes():
    assert STATUS_A["overloaded"] == 529 and retryable(529)
    assert STATUS_B["rate_limited"] == 429 and retryable(429)
    assert not retryable(STATUS_A["invalid_request"])


# ---- streams -------------------------------------------------------

def consume_script(**kw):
    clock, shown = VirtualClock(), []
    res = clock.run(consume(stream(FULL, clock, **kw), shown.append, clock))
    return res, shown, clock


def test_a_cut_at_70_percent_is_incomplete_and_runs_nothing():
    res, shown, _ = consume_script(cut_after=7)
    assert (res.status, res.why) == ("incomplete", "cut")
    assert res.tool_call is None and res.stop is None
    assert shown == ["I can refund order ORD-004830.", " The refund is $15.00."]
    assert res.partial_tool.endswith('"amount_cents": 15')


def test_a_lenient_parser_would_have_made_a_valid_15_cent_refund():
    res, _, _ = consume_script(cut_after=7)
    draft = lenient(res.partial_tool)
    assert draft["amount_cents"] == 15
    assert isinstance(validate_refund_args(draft, "cust-22"), RefundArgs)


def test_a_stalled_stream_is_a_dead_stream_after_the_idle_timeout():
    res, _, clock = consume_script(stall_after=4)
    assert (res.status, res.why) == ("incomplete", "stalled")
    assert 10 <= clock.now() < 11


def test_a_whole_stream_hands_over_its_tool_call_once():
    res, shown, clock = consume_script()
    assert res.status == "complete" and res.stop == "tool"
    assert res.tool_call == GOOD_CALL and len(shown) == 2
    assert clock.now() == pytest.approx(0.5)


def test_an_error_event_after_200_is_not_success():
    events = FULL[:4] + [("error", 529)]
    clock = VirtualClock()

    async def source():
        for e in events:
            yield e
    res = clock.run(consume(source(), lambda s: None, clock))
    assert (res.status, res.why) == ("incomplete", "error")


def test_ending_without_a_stop_event_is_a_cut():
    clock = VirtualClock()

    async def source():
        yield FULL[0]
    res = clock.run(consume(source(), lambda s: None, clock))
    assert (res.status, res.why) == ("incomplete", "cut")


def test_the_last_words_are_shown_when_the_stop_event_arrives():
    clock, shown = VirtualClock(), []

    async def source():
        yield "text", "Done."
        yield "text", " Anything else"
        yield "stop", "end"
    res = clock.run(consume(source(), shown.append, clock))
    assert res.status == "complete" and shown == ["Done.", " Anything else"]
    assert res.tool_call is None


def test_a_stop_event_with_broken_json_is_still_incomplete():
    clock = VirtualClock()

    async def source():
        yield "tool_delta", '{"order_id": '
        yield "stop", "tool"
    res = clock.run(consume(source(), lambda s: None, clock))
    assert (res.status, res.why) == ("incomplete", "bad_json")
    assert res.tool_call is None


def test_consume_leaves_no_stray_tasks():
    clock = VirtualClock()

    async def main():
        await consume(stream(FULL, clock, stall_after=4),
                      lambda s: None, clock)
        await asyncio.sleep(0)
        return len(asyncio.all_tasks())
    assert clock.run(main()) == 2        # this coroutine and the driver


def test_recovery_never_reruns_a_step_with_a_side_effect():
    cut = StreamResult("incomplete", ["One."], partial_tool="{")
    text = StreamResult("incomplete", ["One."])
    nothing = StreamResult("incomplete")
    assert recovery(cut)[0] == "restart"
    assert recovery(text)[0] == "resume"
    assert recovery(nothing)[0] == "restart"
    assert recovery(text, effect_done=True)[0] == "confirm"
    assert recovery(cut, outcome_unknown=True)[0] == "check"


# ---- cancellation --------------------------------------------------

def run_cancel(handler, at):
    clock, log = VirtualClock(), fresh_log()
    clock.run(gateway(handler, log, clock, at))
    return log


def test_a_stream_nobody_owns_keeps_generating_for_40_seconds():
    log = run_cancel(handle_leaky, 3.05)
    assert log["status"] == "cancelled"          # the telemetry says so
    assert log["tokens_at_cancel"] == 30
    assert log["tokens"] - log["tokens_at_cancel"] == 400
    assert round(log["closed_at"] - log["cancelled_at"]) == 40


def test_cancellation_reaches_the_stream_the_retry_and_the_tool_step():
    log = run_cancel(handle_chat, 3.05)
    assert log["status"] == "cancelled"
    assert log["tokens"] == log["tokens_at_cancel"] == 30
    assert log["closed_at"] == log["cancelled_at"]
    assert not log["retry_ran"] and not log["tool_started"]


def test_a_payment_in_flight_finishes_before_the_cancel_is_obeyed():
    log = run_cancel(refund_step, 0.2)
    assert log["refund"] == "paid" and log["status"] == "cancelled"


def test_cancelled_calls_do_not_trip_the_breaker():
    br = CircuitBreaker(clock=FakeClock())
    for _ in range(10):
        record_outcome(br, "cancelled")
    assert br.state == "closed" and br.failures == 0
    for _ in range(5):
        record_outcome(br, "failed")
    assert br.state == "open"


def test_the_cancellation_run_is_deterministic():
    runs = [run_cancel(handle_chat, 3.05) for _ in range(5)]
    assert all(r == runs[0] for r in runs)


def test_virtual_time_orders_wakeups_and_detects_a_stuck_run():
    clock, order = VirtualClock(), []

    async def napper(name, s):
        await clock.sleep(s)
        order.append(name)

    async def main():
        await asyncio.gather(napper("b", 2), napper("a", 1),
                             napper("c", 3))
    clock.run(main())
    assert order == ["a", "b", "c"] and clock.now() == 3

    async def stuck():
        await asyncio.get_running_loop().create_future()
    with pytest.raises(RuntimeError, match="stuck"):
        VirtualClock().run(stuck())


# ---- one request through the incident ------------------------------

def serve_once(world, req=MARIA):
    clock, lines = world.clock, []
    done = clock.run(serve(world, req, "cust-22", "conv-1", lines.append))
    return done, lines


def test_marias_request_pays_exactly_once_and_never_leaves_the_eu():
    world = World(VirtualClock())
    done, lines = serve_once(world)
    assert world.payments.calls == [("ORD-004830", 1500)]
    assert done["amount_cents"] == 1500
    assert world.calls == {"Provider B": 2} and world.violations == 0
    assert world.breakers["Provider A"].state == "open"
    assert lines[1] == "route: Provider B"


def test_an_empty_retry_budget_hands_off_instead_of_retrying():
    world = World(VirtualClock())
    world.retries.tokens = 0.0
    done, lines = serve_once(world)
    assert done is None and world.payments.calls == []
    assert lines[-1] == "retry budget empty: hand off to a human"


def test_no_eligible_provider_degrades_instead_of_routing():
    world = World(VirtualClock())
    world.catalog[1].in_flight = 40
    done, lines = serve_once(world)
    assert done is None and world.payments.calls == []
    assert lines[-1].endswith("tier 2")


# ---- reading a vendor's promises -----------------------------------

def test_sla_arithmetic():
    assert allowed_downtime_minutes(0.999, 30) == pytest.approx(43.2)
    assert allowed_downtime_minutes(0.995, 28) == pytest.approx(201.6)
    assert chained(0.999, 0.999) == pytest.approx(0.999999)


def test_the_demo_prints_the_same_thing_every_time():
    outputs = []
    for _ in range(2):
        buf = io.StringIO()
        with redirect_stdout(buf):
            demo.main()
        outputs.append(buf.getvalue())
    assert outputs[0] == outputs[1] and "residency violations: 0" in outputs[0]
