"""Chapter 16 as tests.   pytest -q ch16_release"""
import io
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date

import pytest

from common.clock import FakeClock
from ch10_providers.vtime import VirtualClock
from ch12_slos.budget import budget_left, error_budget
from ch16_release import demo
from ch16_release.bundle import (PARTS, Registry, changed_parts, digest,
                                 drift, make_bundle)
from ch16_release.canary import (GUARDS, Canary, Guard, budget_at_risk,
                                 verdict)
from ch16_release.capstone import (BASELINE, MEASURED, eval_gate,
                                   month_left, shadow_rung, start,
                                   upgrade)
from ch16_release import faulty
from ch16_release.faulty import (FAULTS, FULL, FaultyProvider, RateLimited,
                                 attempt, consume, run_experiment,
                                 seed_check)
from ch16_release.lifecycle import migration_plan, notice_days
from ch16_release.policy import Change, release_check
from ch16_release.relay_parts import PROMPT_V14, PROMPT_V15, contents
from ch16_release.scorecard import (Candidate, api_cost, breakeven_tasks,
                                    choose, out_reasons, per_resolved,
                                    self_hosted_cost, table)
from ch16_release.shadow import shadow
from ch16_release.traffic import (CONTROL, FRIDAY, V2_TUNED, V2_UNTUNED,
                                  Outcome, counts, make_chats, rate)


# ---- traffic -------------------------------------------------------

def test_the_friday_tweak_doubles_the_reschedule_share():
    chats = make_chats(20_000)
    old = rate([CONTROL.serve(c) for c in chats], "acted")[0]
    new = rate([FRIDAY.serve(c) for c in chats], "acted")[0]
    assert 0.17 < old < 0.19          # about 18% of conversations
    assert 0.36 < new < 0.38          # about 37%


def test_the_same_chat_gives_the_same_outcome_for_one_version():
    chat = make_chats(5)[3]
    assert FRIDAY.serve(chat) == FRIDAY.serve(chat)


def test_audited_flags_are_unknown_unless_the_chat_was_sampled():
    chats = make_chats(500)
    for chat in chats:
        out = FRIDAY.serve(chat)
        assert (out.false_act is None) == (not chat.audited)
        if not (chat.audited and chat.policy_q):
            assert out.wrong_policy is None
    bad, graded = counts([FRIDAY.serve(c) for c in chats], "false_act")
    assert graded == sum(c.audited for c in chats)


# ---- shadow --------------------------------------------------------

def test_shadow_of_the_friday_tweak_finds_one_sided_disagreement():
    r = shadow(make_chats(2000), CONTROL, FRIDAY, "acted", resamples=300)
    assert r.better == 0 and r.worse == 364      # new acts, old does not
    assert r.p_flips < 1e-6
    assert r.interval[0] > 0.15                  # paired interval is tight
    assert r.disagree == pytest.approx(0.182)


def test_shadow_of_a_version_against_itself_is_silent():
    r = shadow(make_chats(500), CONTROL, CONTROL, "acted", resamples=100)
    assert r.disagree == 0 and r.diff == 0 and r.examples == []


def test_shadow_only_grades_chats_both_versions_graded():
    chats = make_chats(2000)
    r = shadow(chats, CONTROL, V2_UNTUNED, "wrong_policy", resamples=200)
    assert r.n == sum(c.audited and c.policy_q for c in chats) == 171
    assert (r.worse, r.better) == (15, 2)
    assert r.p_flips == pytest.approx(0.0023, abs=1e-4)


def test_the_tuned_prompt_passes_shadow():
    r = shadow(make_chats(2000), CONTROL, V2_TUNED, "wrong_policy",
               resamples=200)
    assert r.p_flips > 0.05


# ---- canary --------------------------------------------------------

def outs(bad, n, flag="invalid"):
    """n outcomes where `bad` of them have the flag set."""
    base = Outcome(False, False, False, False, False, None, None)
    return [replace(base, **{flag: i < bad}) for i in range(n)]


def test_verdict_waits_when_there_is_too_little_to_judge():
    guard = Guard("invalid", "invalid", 0.01)
    assert verdict(guard, outs(5, 20), outs(0, 2000)) == "wait"


def test_verdict_is_worse_only_when_even_the_kind_end_is_over_margin():
    guard = Guard("invalid", "invalid", 0.01)
    assert verdict(guard, outs(40, 200), outs(30, 2000)) == "worse"
    # 6% against 1.5%: worse than control, but is it past the margin?
    assert verdict(guard, outs(3, 50), outs(30, 2000)) == "wait"


def test_verdict_is_ok_when_even_the_harsh_end_is_inside_the_margin():
    guard = Guard("invalid", "invalid", 0.01)
    assert verdict(guard, outs(30, 2000), outs(150, 10_000)) == "ok"
    # the same rates on 1,000 chats cannot yet rule out a 1-point loss
    assert verdict(guard, outs(15, 1000), outs(150, 10_000)) == "wait"


def test_zero_bad_chats_in_thirty_is_not_proof():
    guard = Guard("unasked action", "false_act", 0.02)
    canary, control = outs(0, 30, "false_act"), outs(0, 600, "false_act")
    assert verdict(guard, canary, control) == "wait"


def test_failed_chats_are_compared_with_the_control():
    assert any(g.flag == "failed" for g in GUARDS)
    for seed in range(10):
        bad = replace(CONTROL, name="fails 4%", p_fail=0.04)
        res = Canary(CONTROL, bad, FakeClock(), seed=seed).run()
        assert res.decision == "rolled back"
        assert res.reason == "failed chats: clearly worse"
        assert res.failed < 20


def test_a_two_percent_failure_rate_never_reaches_everyone():
    for seed in range(10):
        bad = replace(CONTROL, name="fails 2%", p_fail=0.02)
        res = Canary(CONTROL, bad, FakeClock(), seed=seed).run()
        assert res.decision != "promoted"


def test_the_friday_tweak_is_rolled_back_at_five_percent():
    clock = FakeClock()
    res = Canary(CONTROL, FRIDAY, clock).run()
    assert res.decision == "rolled back"
    assert res.reason == "unasked action: clearly worse"
    assert (res.minutes, res.share, res.exposed) == (25, 0.05, 135)
    assert clock.now() == 25 * 60                # injected, not real time
    assert res.unasked == 27                     # the side effects remain


def test_the_failed_chats_guard_stops_a_high_error_rate_first():
    flaky = replace(CONTROL, name="flaky candidate", p_fail=0.08)
    res = Canary(CONTROL, flaky, FakeClock()).run()
    assert res.decision == "rolled back"
    assert res.reason == "failed chats: clearly worse"
    assert (res.minutes, res.exposed, res.failed) == (5, 31, 7)


def test_the_burn_rate_rule_is_a_fast_trip_on_its_own():
    flaky = replace(CONTROL, name="flaky", p_fail=0.08)
    res = Canary(CONTROL, flaky, FakeClock(), guards=()).run()
    assert res.decision == "rolled back" and res.reason.startswith("burn")
    assert res.failed >= 8


def test_the_burn_rate_guard_needs_enough_chats():
    from ch12_slos.burn import Series
    from ch16_release.canary import burning
    clock = FakeClock()
    series = Series(clock)
    for _ in range(10):
        clock.sleep(60)
        series.record(5, 10)          # 50% failing, but only 100 chats
    assert burning(series, min_chats=100) is not None
    assert burning(series, min_chats=500) is None


def test_an_unchanged_candidate_is_not_rolled_back():
    for seed in range(20):
        res = Canary(CONTROL, CONTROL, FakeClock(), seed=seed).run()
        assert res.decision == "promoted"


def test_a_good_candidate_ramps_through_every_step():
    res = Canary(CONTROL, V2_TUNED, FakeClock()).run()
    assert res.decision == "promoted"
    assert res.log == [(30, 0.05), (60, 0.25), (115, 0.5)]


def test_only_the_last_step_needs_every_guard_to_say_ok():
    never_ok = (Guard("slow first token", "slow", 0.0),)   # A/A: hi > 0
    res = Canary(CONTROL, CONTROL, FakeClock(), guards=never_ok).run()
    assert [s for _, s in res.log] == [0.05, 0.25]
    assert res.decision == "held" and res.share == 0.5


def test_a_looser_margin_is_slower_to_roll_back():
    def run(margin):
        guards = (Guard("reschedule share", "acted", margin),)
        return Canary(CONTROL, FRIDAY, FakeClock(), guards=guards).run()
    tight, loose = run(0.02), run(0.10)
    assert (tight.minutes, tight.exposed, tight.unasked) == (25, 135, 27)
    assert (loose.minutes, loose.exposed, loose.unasked) == (40, 413, 79)
    assert loose.decision == "rolled back"


def test_looking_every_five_minutes_with_no_margin_cries_wolf():
    zero = (Guard("reschedule share", "acted", 0.0),)
    rolled = [Canary(CONTROL, CONTROL, FakeClock(), seed=s,
                     guards=zero).run(limit=240).decision == "rolled back"
              for s in range(20, 40)]
    assert sum(rolled) >= 2            # a false alarm with no real change


def test_a_canary_that_cannot_decide_is_held_not_promoted():
    res = Canary(CONTROL, V2_TUNED, FakeClock()).run(limit=20)
    assert res.decision == "held" and res.reason == "time limit"


def test_budget_at_risk_scales_with_exposure():
    assert budget_at_risk(0.05, 45, 100, 0.08) == 18
    assert budget_at_risk(1.0, 45, 100, 0.08) == 360
    allowed = error_budget(0.995, 1_000_000)
    assert 360 / allowed == pytest.approx(0.072)


# ---- rehearse failure ---------------------------------------------

@pytest.fixture(scope="module")
def run_one():
    return run_experiment()


@pytest.fixture(scope="module")
def run_two():
    return run_experiment(failover=True)


def test_run_one_breaks_the_hypothesis(run_one):
    run = run_one
    assert len(run.failed) == 74 and run.availability == 0.963
    assert not run.holds and run.ran_from_partial == 0
    assert run.injected == {"rate_limited": 126, "timeout": 49,
                            "stream_cut": 48, "bad_json": 46}
    assert run.drafts == 48 + 46       # every cut and broken call held


def test_failing_over_when_retries_run_out_holds(run_two):
    run = run_two
    assert len(run.failed) == 2 and run.availability == 0.999
    assert run.holds
    assert run.first_token_rate >= 0.95


def test_one_seed_is_one_draw_and_the_finding_survives_ten():
    checks = seed_check()
    assert len(checks) == 10
    assert all(one > 10 for one, _ in checks)      # run 1 always breaks
    assert all(two <= 10 for _, two in checks)     # run 2 always holds


def test_broken_json_is_a_failed_chat_unless_a_repair_works():
    run = run_experiment(n=100, faults={"bad_json": 1.0})
    assert run.availability == 0.0                 # never counted as ok
    assert run.drafts == run.injected["bad_json"]


def test_every_second_try_is_paid_from_the_retry_budget():
    run = run_experiment(n=500, faults={"stream_cut": 1.0})
    calls = run.injected["stream_cut"]
    assert calls <= 500 + 5 + 0.1 * 500            # burst 5, refill 10%


def test_a_tool_call_from_an_unfinished_stream_is_counted(monkeypatch):
    async def lenient_consume(events, show, clock=None):
        res = await consume(events, show, clock)
        if res.status != "complete" and res.partial_tool:
            res.tool_call = {"draft": res.partial_tool}   # do not do this
        return res
    monkeypatch.setattr(faulty, "consume", lenient_consume)
    run = run_experiment(n=300)
    assert run.ran_from_partial > 0 and not run.holds


def test_the_experiment_is_repeatable():
    a, b = run_experiment(n=300), run_experiment(n=300)
    assert a.failed == b.failed and a.injected == b.injected


def test_the_figure_uses_the_failures_the_experiment_produced(run_one,
                                                              run_two):
    assert run_one.failed[:6] == [20, 28, 71, 72, 110, 111]
    assert run_two.failed == [457, 1126]


def test_a_stop_condition_ends_a_runaway_experiment_early():
    run = run_experiment(faults={"rate_limited": 0.30, "timeout": 0.02},
                         stop_after=3)
    assert run.chats == 11 and len(run.failed) == 3
    assert run.aborted == "3 failed chats within 50"
    calm = run_experiment(n=300, failover=True, stop_after=3)
    assert calm.aborted == "" and calm.chats == 300


def test_virtual_time_costs_nothing():
    clock = VirtualClock()
    provider = FaultyProvider(clock, {"timeout": 1.0}, seed=1)
    res = clock.run(provider.chat())
    assert res.status == "incomplete" and res.why == "stalled"
    assert clock.now() > 10                      # ten virtual seconds


def test_each_fault_shows_up_as_chapter_ten_describes_it():
    def one(fault):
        clock = VirtualClock()
        provider = FaultyProvider(clock, {fault: 1.0}, seed=1)
        return clock.run(attempt(provider))
    results = {f: one(f) for f in FAULTS}
    assert results == {"rate_limited": "retry", "timeout": "retry",
                       "stream_cut": "cut", "bad_json": "bad_json"}


def test_a_provider_with_no_faults_always_completes():
    clock = VirtualClock()
    provider = FaultyProvider(clock, {}, seed=3)
    res = clock.run(provider.chat())
    assert res.status == "complete" and res.tool_call["amount_cents"] == 1500
    assert [e[0] for e in FULL][-1] == "stop"


def test_a_rate_limit_arrives_before_any_stream():
    clock = VirtualClock()
    provider = FaultyProvider(clock, {"rate_limited": 1.0}, seed=1)
    with pytest.raises(RateLimited):
        clock.run(provider.chat())
    assert provider.first_tokens == []


# ---- the error-budget check ---------------------------------------

@pytest.mark.parametrize("left, flight, expected", [
    (0.62, 0, "ship"), (0.51, 1, "ship"), (0.50, 0, "ship"),
    (0.36, 0, "ship"), (0.36, 1, "hold"), (0.25, 1, "hold"),
    (0.22, 0, "hold"), (0.0, 0, "hold"), (-0.2, 0, "hold")])
def test_a_model_upgrade_asks_the_ladder(left, flight, expected):
    model = Change("model", "a-large-v2")
    assert release_check(model, left, flight)[0] == expected


def test_fixes_ship_on_every_rung_and_nothing_else_below_a_quarter():
    fix = Change("security_fix", "patch")
    assert all(release_check(fix, x)[0] == "ship"
               for x in (0.9, 0.4, 0.1, 0.0))
    routine = Change("docs", "runbook typo")
    assert release_check(routine, 0.1)[0] == "hold"
    assert release_check(routine, 0.0)[0] == "hold"


@pytest.mark.parametrize("kind", ["model", "docs", "reliability_fix"])
def test_the_ladder_never_loosens_as_the_error_budget_falls(kind):
    levels = (0.9, 0.6, 0.5, 0.4, 0.25, 0.2, 0.1, 0.0, -0.1)
    held = [release_check(Change(kind, "x"), x, 1)[0] == "hold"
            for x in levels]
    assert held == sorted(held)        # once held, held all the way down


def test_every_kind_of_change_is_a_release():
    for kind in ("prompt", "model", "tool_schema", "index", "threshold"):
        assert Change(kind, "x").risky
    assert release_check(Change("prompt", "v15"), 0.0)[0] == "hold"


def test_the_budget_left_comes_from_the_months_counts():
    assert month_left() == budget_left(0.995, 1_000_000, 1900) == 0.62


# ---- the bundle ----------------------------------------------------

def make(prompt=PROMPT_V14, model="a-large-v1", label="prompt v14",
         bundle_id="R-117"):
    return make_bundle(bundle_id, contents(prompt, model, label),
                       "Relay-60 v3", "judge v2")


def test_a_bundle_needs_all_six_parts():
    parts = contents(PROMPT_V14, "a-large-v1", "prompt v14")
    del parts["tools"]
    with pytest.raises(ValueError, match="tools"):
        make_bundle("R-1", parts, "set", "judge")
    assert PARTS == ("prompt", "model", "tools", "index", "policy",
                     "config")


def test_the_fingerprint_is_stable_and_changes_with_any_part():
    assert make().fingerprint() == make().fingerprint()
    assert make().fingerprint() != make(prompt=PROMPT_V15).fingerprint()
    assert make().fingerprint() != make(model="a-large-v2").fingerprint()


def test_changed_parts_names_what_moved():
    old = make()
    new = make(PROMPT_V15, "a-large-v2", "prompt v15", "R-118")
    assert changed_parts(old, new) == [
        "prompt: prompt v14 -> prompt v15", "model: a-large-v1 -> a-large-v2"]
    assert changed_parts(old, make(bundle_id="R-999")) == []


def test_drift_catches_an_edit_nobody_versioned():
    parts = contents(PROMPT_V14, "a-large-v1", "prompt v14")
    bundle = make()
    live = {p: body for p, (_, body) in parts.items()}
    assert drift(bundle, live) == []
    live["prompt"] += " Be more proactive."
    assert drift(bundle, live) == ["prompt"]
    assert digest({"a": 1}) == digest({"a": 1}) != digest({"a": 2})


def test_roll_back_restores_the_whole_combination():
    registry = Registry()
    old, new = make(), make(PROMPT_V15, "a-large-v2", "prompt v15", "R-118")
    registry.promote(old)
    registry.promote(new)
    back = registry.roll_back()
    assert back is old and back.fingerprint() == old.fingerprint()
    with pytest.raises(RuntimeError):
        registry.roll_back()


# ---- the life of a model ------------------------------------------

def test_a_notice_window_and_the_plan_inside_it():
    assert notice_days(date(2026, 9, 30), date(2026, 11, 30)) == 61
    assert [d for d, _ in migration_plan(61)] == [6, 15, 24, 34, 46, 55]
    plan = migration_plan(60)
    assert [d for d, _ in plan] == [6, 15, 24, 33, 45, 54]
    assert [d for d, _ in migration_plan(80)] == [8, 20, 32, 44, 60, 72]


CANDIDATES = [
    Candidate("a-large-v1", 182, api_cost(6.0, 5000), 1.4, 4, 30),
    Candidate("a-large-v2 p14", 172, api_cost(4.6, 5000), 1.1, 20, 30),
    Candidate("a-large-v2 p15", 182, api_cost(4.6, 5400), 1.1, 20, 30),
    Candidate("a-small-v1", 156, api_cost(1.2, 6500), 0.7, 20, 30),
    Candidate("b-large (EU)", 182, api_cost(8.0, 5000), 1.5, 14, 0),
    Candidate("open-70b (ours)", 168,
              self_hosted_cost(24_600, 0.004, 900_000), 1.9, 99, 0)]


def test_hard_limits_come_before_cost():
    why = {c.name: out_reasons(c) for c in CANDIDATES}
    assert why["a-large-v1"] == ["life"]
    assert why["a-large-v2 p14"] == ["quality"]
    assert why["a-small-v1"] == ["quality"]
    assert why["a-large-v2 p15"] == [] == why["b-large (EU)"]
    cheapest = min(CANDIDATES, key=per_resolved)
    assert cheapest.name == "a-small-v1"         # cheap and not eligible
    assert choose(CANDIDATES).name == "a-large-v2 p15"


def test_the_scorecard_never_makes_a_small_model_dearer_per_token():
    assert api_cost(1.2, 1000) < api_cost(4.6, 1000) < api_cost(6.0, 1000)
    assert per_resolved(CANDIDATES[2]) == pytest.approx(
        api_cost(4.6, 5400) / 0.91)
    assert len(table(CANDIDATES)) == len(CANDIDATES)


def test_build_or_buy_turns_on_volume():
    v2 = api_cost(4.6, 5000)
    even = breakeven_tasks(24_600, v2, 0.004)
    assert even == pytest.approx(1_294_737, abs=1)
    assert even > 900_000                       # Crateway is below it
    assert breakeven_tasks(12_300, v2, 0.004) < 900_000
    assert self_hosted_cost(24_600, 0.004, even) == pytest.approx(v2)


def test_choose_returns_none_when_nobody_is_eligible():
    assert choose([CANDIDATES[0], CANDIDATES[1]]) is None


# ---- the capstone --------------------------------------------------

def test_the_old_baseline_and_the_untuned_model_fail_the_gate():
    gate = eval_gate(MEASURED["a-large-v2, prompt v14"])
    assert not gate.passed and "quality" in gate.detail
    assert eval_gate(MEASURED["a-large-v2, prompt v15"]).passed
    assert BASELINE["quality"] == 0.91


def test_every_rung_would_have_caught_the_straight_swap():
    registry = start()
    rungs, result = upgrade("a-large-v2, prompt v14", month_left(),
                            registry, stop=False)
    verdicts = {r.name: r.passed for r in rungs}
    assert verdicts == {"eval gate": False, "rehearsal": True,
                        "shadow": False, "error budget": True,
                        "bundle": True, "canary": False}
    assert result.decision == "rolled back" and result.minutes == 45
    assert result.exposed == 529
    assert registry.live.id == "R-117"           # nothing was promoted


def test_an_inconclusive_shadow_waits_and_never_passes():
    short = shadow_rung(V2_TUNED, n=2000)        # 171 graded chats
    assert short.says == "wait" and short.passed  # the next rung decides
    assert "(-1.2 to +4.1)" in short.detail      # past the 3-point margin
    assert shadow_rung(V2_TUNED).says == "pass"
    assert shadow_rung(V2_UNTUNED).says == "STOP"


def test_each_upgrade_gets_a_bundle_id_of_its_own():
    swap, tuned = start(), start()
    upgrade("a-large-v2, prompt v14", month_left(), swap, stop=False)
    upgrade("a-large-v2, prompt v15", month_left(), tuned)
    assert tuned.live.id == "R-119" and swap.live.id == "R-117"


def test_the_ladder_stops_at_the_first_failed_rung():
    registry = start()
    rungs, result = upgrade("a-large-v2, prompt v14", month_left(),
                            registry)
    assert result is None and rungs[-1].name == "bundle"
    assert registry.live.id == "R-117"


def test_the_tuned_upgrade_ships_and_can_be_rolled_back():
    registry = start()
    before = registry.live.fingerprint()
    rungs, result = upgrade("a-large-v2, prompt v15", month_left(),
                            registry)
    assert all(r.passed for r in rungs)
    assert result.decision == "promoted" and registry.live.id == "R-119"
    assert registry.roll_back().fingerprint() == before


def test_a_model_upgrade_is_held_when_the_budget_is_thin():
    registry = start()
    rungs, result = upgrade("a-large-v2, prompt v15", 0.22, registry)
    assert result is None
    assert [r.name for r in rungs if not r.passed] == ["error budget"]


# ---- the demo ------------------------------------------------------

def test_the_demo_prints_the_numbers_the_chapter_quotes():
    buf = io.StringIO()
    with redirect_stdout(buf):
        demo.main()
    out = buf.getvalue()
    for line in ("run 1: 96.3% available (74 of 2,000 failed)",
                 "run 2, failover to B: 99.9% available (2 of 2,000 failed)",
                 "partial tool calls: 94 held, 0 run",
                 "10 seeds: run 1 broke it in 10 (52 to 88 failed), "
                 "run 2 in 0 (0 to 4)",
                 "rolled back at minute 25: unasked action",
                 "control against itself, 50 seeds: 0 rolled back",
                 "rollback drill: live R-117",
                 "choice: a-large-v2 p15"):
        assert line in out
    assert max(len(x) for x in out.splitlines()) <= 74
