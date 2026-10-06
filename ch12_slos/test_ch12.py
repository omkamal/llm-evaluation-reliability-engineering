"""Chapter 12 as tests.   pytest -q ch12_slos"""
import random

import pytest

from common.clock import FakeClock
from ch12_slos import demo
from ch12_slos.budget import (budget_left, burn_rate, days_to_empty,
                              error_budget, policy_rung, share_spent)
from ch12_slos.burn import (MIN_CHATS, RULES, Rule, Series,
                            alert_decision, long_window_only,
                            minutes_to_alert, minutes_to_clear)
from ch12_slos.health import Dependency, deep, shallow
from ch12_slos.quality import (cost_per_success, daily_reads,
                               judge_corrected, judge_reading,
                               judge_verdict, refusal_rate)
from ch12_slos.report import Spend, render_report
from ch12_slos.sheet import SHEET, check_sheet, line
from ch12_slos.tasks import (Task, cost_per_resolved, per_task, percentile,
                             share_within, simulate_calls)


# ---- the error budget -------------------------------------------------

def test_the_two_budgets_in_the_chapter():
    assert error_budget(0.995, 1_000_000) == 5_000      # chat layer
    assert error_budget(0.99, 840_000) == 8_400         # task layer, 28 d
    assert error_budget(0.99, 30_000 * 28) == 8_400     # 30,000 a day


def test_burn_rate_arithmetic():
    burn = burn_rate(72, 1000, 0.995)
    assert round(burn, 6) == 14.4
    assert round(days_to_empty(burn), 2) == 1.94
    assert round(share_spent(burn, 1), 3) == 0.021
    assert days_to_empty(1.0) == 28
    assert burn_rate(0, 0, 0.995) == 0.0


def test_a_100_percent_slo_is_refused_not_divided_by_zero():
    with pytest.raises(ValueError):
        burn_rate(1, 100, 1.0)
    with pytest.raises(ValueError):
        budget_left(1.0, 1_000_000, 0)
    with pytest.raises(ValueError):
        alert_decision(demo.spike_series(5), slo=1.0)


def test_each_tier_spends_a_known_share_of_the_28_day_budget():
    shares = [share_spent(r.burn, r.long_s / 3600) for r in RULES]
    assert [round(x, 3) for x in shares] == [0.021, 0.054, 0.107]


def test_a_leak_below_one_percent_empties_the_budget_early():
    burn = burn_rate(8, 1000, 0.995)                    # 0.8% failing
    assert round(burn, 6) == 1.6
    assert round(days_to_empty(burn), 1) == 17.5


def test_the_fast_tier_cannot_fire_on_a_low_target():
    budget = 1 - 0.90                                   # a 90% judge SLO
    assert round(14.4 * budget, 6) == 1.44              # 144% of answers
    assert round(6 * budget, 6) == 0.6


def test_budget_left_and_the_policy_ladder():
    assert budget_left(0.995, 1_000_000, 1_900) == 0.62
    assert policy_rung(0.62) == "ship features"
    assert policy_rung(0.50).startswith("ship, one risky")
    assert policy_rung(0.25).startswith("ship, one risky")
    assert policy_rung(0.24) == "reliability fixes only"
    assert policy_rung(0.0) == "freeze risky releases"
    assert policy_rung(-0.1) == "freeze risky releases"


# ---- windows, rules and decisions ---------------------------------

def test_series_sums_the_buckets_inside_a_window():
    clock = FakeClock()
    series = Series(clock)
    for minute in range(10):
        clock.sleep(60)
        series.record(minute, 100)
    assert series.window(300) == (5 + 6 + 7 + 8 + 9, 500)
    assert series.window(10_000) == (45, 1000)


def spike(failing_minutes, bad=8):
    clock = FakeClock()
    series = Series(clock)
    for _ in range(4320):
        clock.sleep(60)
        series.record(0, 100)
    for _ in range(failing_minutes):
        clock.sleep(60)
        series.record(bad, 100)
    return series


def test_the_worked_example_pages_at_minute_55():
    series = spike(55)
    assert series.window(3600) == (440, 6000)
    assert series.window(300) == (40, 500)
    decision = alert_decision(series)
    assert decision.action == "page" and decision.rule.burn == 14.4
    assert decision.long_burn == 14.666667 and decision.short_burn == 16.0
    assert alert_decision(spike(54)).action == "ok"


def test_time_to_first_alert_by_failure_rate():
    expected = {1.0: 5, 0.20: 22, 0.08: 55, 0.07: 155, 0.04: 271,
                0.01: 2161}
    for rate, minutes in expected.items():
        assert minutes_to_alert(rate)[0] == minutes
    assert minutes_to_alert(0.04)[1].rule.burn == 6.0
    assert minutes_to_alert(0.01)[1].action == "ticket"


def test_a_slow_leak_that_is_on_pace_never_alerts():
    # 0.4% of 1,000 chats is four real failures a minute, for four days
    minute, decision = minutes_to_alert(0.004, per_minute=1000)
    assert minute is None and decision.action == "ok"
    # a just-faster leak does alert, so the run above is not vacuous
    assert minutes_to_alert(0.006, per_minute=1000)[1].action == "ticket"


def test_a_rate_that_rounds_to_zero_failures_is_refused():
    with pytest.raises(ValueError):
        minutes_to_alert(0.004, per_minute=100)         # 0.4 of a chat
    with pytest.raises(ValueError):
        minutes_to_clear(RULES, failure_rate=0.004)


def test_history_has_the_same_volume_as_the_failing_traffic():
    # before the fix, history stayed at 100 a minute: a ticket at 618
    assert minutes_to_alert(0.008, per_minute=1000)[0] == 2701
    assert minutes_to_alert(0.08, per_minute=1000)[0] == 55
    assert minutes_to_alert(0.08, per_minute=100)[0] == 55


def test_minutes_to_clear_stops_when_nothing_fires():
    assert minutes_to_clear(RULES, failure_rate=0.05) == (None, None)


# ---- few chats: the floor ------------------------------------------

def test_the_floor_is_the_100_chats_chapter_16_relies_on():
    assert MIN_CHATS == 100


def test_one_failure_on_a_quiet_night_pages_only_without_a_floor():
    clock, series = demo.quiet_night()                  # 12 chats an hour
    clock.sleep(300)
    series.record(1, 1)                                 # one chat fails
    bare = alert_decision(series, min_chats=0)
    assert bare.action == "page" and bare.long_burn == 16.666667
    assert alert_decision(series).action == "ok"


def test_five_failures_at_one_chat_a_minute_page_only_without_a_floor():
    clock, series = demo.quiet_night(gap_s=60)
    for _ in range(5):
        clock.sleep(60)
        series.record(1, 1)
    assert alert_decision(series, min_chats=0).action == "page"
    assert alert_decision(series).action == "ok"        # 60 chats an hour


def test_a_real_outage_on_a_quiet_night_still_alerts():
    minutes, decision = demo.outage_alert_minutes()     # 12 an hour
    assert (minutes, decision.action) == (25, "ticket")
    minutes, decision = demo.outage_alert_minutes(60)   # 60 an hour
    assert (minutes, decision.action) == (11, "page")
    assert decision.rule.burn == 6.0


def test_the_floor_counts_the_long_window_and_lets_100_through():
    clock = FakeClock()
    series = Series(clock)
    for _ in range(100):                                # 100 chats in 1 h
        clock.sleep(36)
        series.record(1, 1)
    assert series.window(3600)[1] == 100
    assert alert_decision(series).action == "page"


def test_a_short_outage_does_not_page_but_a_short_window_alone_would():
    clock = FakeClock()
    series = Series(clock)
    for _ in range(4320):
        clock.sleep(60)
        series.record(0, 100)
    for _ in range(3):
        clock.sleep(60)
        series.record(100, 100)
    assert alert_decision(series).action == "ok"
    five_minutes_only = (Rule("page", 14.4, 300, 300),)
    assert alert_decision(series, rules=five_minutes_only).action == "page"


def test_both_windows_must_agree():
    # long window hot, short window cool: the fire is already out
    series = spike(30, bad=20)
    clock = series.clock
    for _ in range(6):
        clock.sleep(60)
        series.record(0, 100)
    assert series.window(3600)[0] == 600                # long still hot
    assert alert_decision(series).action == "ok"
    assert alert_decision(series, rules=long_window_only()).action == "page"


def test_short_window_clears_fast_long_window_clears_slowly():
    assert minutes_to_clear(RULES) == (22, 4)
    assert minutes_to_clear(long_window_only()) == (22, 39)


def test_no_data_is_not_an_alert():
    assert alert_decision(Series(FakeClock())).action == "ok"


# ---- per task, quality and the sheet -------------------------------

def test_per_call_latency_hides_what_the_task_feels():
    calls, resolved = simulate_calls()
    tasks = per_task(calls, resolved)
    call_p95 = percentile([c.seconds for c in calls], 95)
    task_p95 = percentile([t.seconds for t in tasks], 95)
    assert len(tasks) == 2000 and len(calls) == 11_011
    assert call_p95 < 2.0 < 8.0 < task_p95
    assert round(share_within([t.seconds for t in tasks], 8), 3) == 0.893


def test_percentile_and_the_mean_that_hides_the_tail():
    first_token = [0.7] * 94 + [6.0] * 6
    assert round(sum(first_token) / 100, 2) == 1.02
    assert percentile(first_token, 95) == 6.0
    assert share_within(first_token, 2) == 0.94


def test_failed_tasks_cost_money_and_are_not_in_the_denominator():
    tasks = [Task(5, 0.05, True), Task(5, 0.05, True), Task(5, 0.05, False)]
    assert round(cost_per_resolved(tasks), 4) == 0.075  # not 0.05


def test_judge_verdicts_use_the_interval_not_the_point():
    assert judge_verdict(4550, 5000, 0.90)[2] == "met"
    rate, (lo, hi), verdict = judge_verdict(4480, 5000, 0.90)
    assert rate < 0.90 and lo < 0.90 < hi and verdict == "unclear"
    assert judge_verdict(4400, 5000, 0.90)[2] == "missed"
    assert round(judge_verdict(4550, 5000, 0.90)[1][0], 3) == 0.902
    assert round(judge_verdict(4480, 5000, 0.90)[1][0], 3) == 0.887


def test_the_correction_undoes_the_judge():
    for tpr, tnr in ((0.97, 0.25), (0.91, 0.94), (0.92, 0.90)):
        reading = judge_reading(0.86, tpr, tnr)
        assert round(judge_corrected(reading, tpr, tnr), 9) == 0.86
    assert round(judge_corrected(0.791, 0.91, 0.94), 3) == 0.86
    # uncorrected, a 90% reading needs 98.8% true quality from this judge
    assert round(judge_corrected(0.90, 0.91, 0.94), 3) == 0.988
    with pytest.raises(ValueError):
        judge_corrected(0.5, 0.5, 0.5)                  # a coin
    assert judge_corrected(0.99, 0.91, 0.94) == 1.0     # clipped


def test_a_corrected_verdict_widens_the_interval():
    raw = judge_verdict(4168, 5000, 0.90)[1]
    fixed = judge_verdict(4168, 5000, 0.90, tpr=0.91, tnr=0.94)
    width = (fixed[1][1] - fixed[1][0]) / (raw[1] - raw[0])
    assert round(width, 3) == round(1 / 0.85, 3)
    assert round(fixed[0], 3) == 0.910                  # reads 83.4%


def ticket_hours(seed, true_good=0.91, per_hour=30, slo=0.90):
    """A month of a 2% judged sample, read by the burn-rate rules."""
    rng, clock = random.Random(seed), FakeClock()
    series, hours = Series(clock), 0
    for hour in range(72 + 672):                    # 3 days of history
        clock.sleep(3600)
        bad = sum(rng.random() > true_good for _ in range(per_hour))
        series.record(bad, per_hour)
        if hour >= 72 and alert_decision(series, slo=slo).action != "ok":
            hours += 1
    return hours


def test_burn_rate_on_a_judged_sample_mostly_measures_luck():
    # true quality 91% meets the 90% line, yet most months open tickets
    months = [ticket_hours(seed) for seed in range(20)]
    assert sum(h > 0 for h in months) == 17


def test_inc4_replayed_through_the_weekly_verdict():
    reads = daily_reads(demo.inc4_good_rates(), 714, 0.90)
    assert reads[:2] == ["met", "met"]                  # before, day 1
    assert reads.index("unclear") == 2
    assert reads.index("missed") == 7                   # Priya: day 9
    assert reads[7:] == ["missed"] * 3


def test_a_judge_reading_is_only_as_true_as_its_tnr():
    weak = judge_reading(0.86, 0.97, 0.25)              # Chapter 5's judge
    assert round(weak, 3) == 0.939 and weak > 0.90 > 0.86
    good = judge_reading(0.86, 0.91, 0.94)
    assert round(good, 3) == 0.791
    assert judge_reading(1.0, 1.0, 0.0) == 1.0


def test_refusals_and_cost_per_success():
    replies = ["ok"] * 984 + ["I can't help."] * 16
    assert refusal_rate(replies) == 0.016
    assert round(cost_per_success(31.20, 980), 4) == 0.0318


def test_the_sheet_matches_relay_facts():
    chat = [s for s in SHEET if s.layer == "chat"]
    task = [s for s in SHEET if s.layer == "task"]
    assert len(chat) == 6 and len(task) == 4
    targets = {s.name: (s.target, s.at_least, s.window_days) for s in SHEET}
    assert targets["availability"] == (99.5, True, 28)
    assert targets["first token within 2 s"] == (95.0, True, 28)
    assert targets["first-pass validity"] == (98.0, True, 28)
    assert targets["answers judged good"] == (90.0, True, 7)
    assert targets["refusals"] == (2.0, False, 7)
    assert targets["cost per success"] == (0.04, False, 7)
    assert targets["task success"] == (99.0, True, 28)
    assert targets["p95 task latency"] == (8.0, False, 28)
    assert targets["judge pass, weekly"] == (90.0, True, 7)
    assert targets["cost per resolved task"] == (0.06, False, 7)


def test_check_sheet_directions_and_lines():
    result = check_sheet({"availability": 99.4, "refusals": 1.4,
                          "p95 task latency": 8.0})
    assert [ok for _, _, ok in result] == [False, True, False]  # "under"
    assert result[0][0].margin(99.4) < 0 < result[1][0].margin(1.4)
    assert line(*result[0]).endswith("MISSED")
    assert "$0.04" in line(SHEET[5], 0.031, True)


# ---- dependencies and the report ----------------------------------

def test_shallow_says_ok_where_deep_says_fail():
    index = Dependency("policy index", True, "no results", "14 days")
    assert shallow(index) and not deep(index)
    down = Dependency("tracking API", False, "", "x")
    assert not shallow(down) and not deep(down)
    fine = Dependency("policy index", True, "returns: 14 days", "14 days")
    assert deep(fine)


def test_report_counts_kept_promises_and_the_spend():
    results = check_sheet({"availability": 99.8, "p95 task latency": 9.0})
    spends = [Spend(1200, True, "a trial"), Spend(700, False, "timeouts")]
    text = "\n".join(render_report("a period", results, 5000, spends,
                                   {"p95 task latency": "too slow"}))
    assert "Promises kept: 1 of 2" in text and "Missed: too slow" in text
    assert "Used 1,900 (38%), left 3,100 (62%)" in text
    assert "on purpose: a trial" in text and "not planned: timeouts" in text
    assert text.endswith("ship features.")


def test_more_unplanned_spend_moves_the_policy_line():
    results = check_sheet({"availability": 99.8})
    spends = [Spend(1200, True, "a"), Spend(700, False, "b"),
              Spend(2000, False, "c")]
    text = "\n".join(render_report("p", results, 5000, spends, {}))
    assert "Used 3,900 (78%), left 1,100 (22%)" in text
    assert text.endswith("reliability fixes only.")


def test_the_demo_runs_and_prints_the_headline_numbers(capsys):
    demo.main()
    out = capsys.readouterr().out
    assert "burn 14.4x" in out and "error budget lasts 1.94 days" in out
    assert "after 55 minutes: page" in out
    assert "Promises kept: 9 of 10" in out
