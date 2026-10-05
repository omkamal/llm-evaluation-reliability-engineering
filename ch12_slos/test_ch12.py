"""Chapter 12 as tests.   pytest -q ch12_slos"""
from common.clock import FakeClock
from ch12_slos import demo
from ch12_slos.budget import (budget_left, burn_rate, days_to_empty,
                              error_budget, policy_rung, share_spent)
from ch12_slos.burn import (RULES, Rule, Series, alert_decision,
                            long_window_only, minutes_to_alert,
                            minutes_to_clear)
from ch12_slos.health import Dependency, deep, shallow
from ch12_slos.quality import (cost_per_success, judge_reading,
                               judge_verdict, refusal_rate)
from ch12_slos.report import Spend, render_report
from ch12_slos.sheet import SHEET, check_sheet, line
from ch12_slos.tasks import (Task, cost_per_resolved, per_task, percentile,
                             share_within, simulate_calls)


# ---- the error budget -------------------------------------------------

def test_the_two_budgets_in_the_chapter():
    assert error_budget(0.995, 1_000_000) == 5_000      # chat layer
    assert error_budget(0.99, 900_000) == 9_000         # task layer, 30 d
    assert error_budget(0.99, 840_000) == 8_400         # same, 28 d


def test_burn_rate_arithmetic():
    burn = burn_rate(72, 1000, 0.995)
    assert round(burn, 6) == 14.4
    assert round(days_to_empty(burn), 2) == 1.94
    assert round(share_spent(burn, 1), 3) == 0.021
    assert days_to_empty(1.0) == 28
    assert burn_rate(0, 0, 0.995) == 0.0


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
    minute, decision = minutes_to_alert(0.004)          # burn 0.8
    assert minute is None and decision.action == "ok"


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
    assert "burn 14.4x" in out and "budget lasts 1.94 days" in out
    assert "after 55 minutes: page" in out
    assert "Promises kept: 9 of 10" in out
