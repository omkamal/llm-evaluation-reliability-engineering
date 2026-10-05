"""Every Chapter 12 output.   python3 -m ch12_slos.demo"""
from common.clock import FakeClock
from ch04_numbers.stats import proportion_ci
from ch12_slos.budget import (burn_rate, days_to_empty, error_budget,
                              policy_rung, share_spent)
from ch12_slos.burn import (RULES, Series, alert_decision, long_window_only,
                            minutes_to_alert, minutes_to_clear)
from ch12_slos.health import Dependency, health_table
from ch12_slos.quality import (cost_per_success, judge_reading,
                               judge_verdict, refusal_rate)
from ch12_slos.report import Spend, render_report
from ch12_slos.sheet import SHEET, check_sheet, line
from ch12_slos.tasks import (Call, cost_per_resolved, per_task, percentile,
                             share_within, simulate_calls)


def hours(minutes):
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if h else f"{m} min"


def demo_tasks():
    print("== per call, then per task")
    calls, resolved = simulate_calls()
    tasks = per_task(calls, resolved)
    secs = [t.seconds for t in tasks]
    print(f"{len(tasks):,} tasks made {len(calls):,} calls")
    print(f"per call: p95 {percentile([c.seconds for c in calls], 95):.1f} s")
    print(f"per task: p95 {percentile(secs, 95):.1f} s (SLO: under 8 s)")
    print(f"tasks within 8 s: {share_within(secs, 8):.1%}")
    spend = sum(t.usd for t in tasks)
    print(f"spend ${spend:.2f}; cost per task ${spend / len(tasks):.4f}, "
          f"per resolved task ${cost_per_resolved(tasks):.4f}")
    return tasks


def demo_percentiles():
    print("== why percentiles")
    first_token = [0.7] * 94 + [6.0] * 6
    mean = sum(first_token) / len(first_token)
    print(f"mean {mean:.2f} s, p95 {percentile(first_token, 95):.2f} s")
    print(f"within 2 s: {share_within(first_token, 2):.0%} (SLO: 95%)")


def demo_quality():
    print("== judged sample, one week each")
    for week, passes in ((1, 4550), (2, 4480), (3, 4400)):
        rate, (lo, hi), verdict = judge_verdict(passes, 5000, 0.90)
        print(f"week {week}: {passes:,} of 5,000 = {rate:.1%} "
              f"({lo:.1%} to {hi:.1%}) {verdict}")
    for name, tpr, tnr in (("Friday's judge", 0.97, 0.25),
                           ("calibrated judge", 0.91, 0.94)):
        reading = judge_reading(0.86, tpr, tnr)
        print(f"true 86%, {name} (TPR {tpr}, TNR {tnr}) reads {reading:.1%}")
    replies = ["Your order ships Monday."] * 984 + ["I can't help."] * 16
    print(f"refusals: {refusal_rate(replies):.1%} of {len(replies)} replies")
    print(f"cost per success: ${31.20 / 980:.4f} (spend $31.20, 980 ok)")


def demo_budget():
    print("== error budget")
    print(f"chat layer: {error_budget(0.995, 1_000_000):,} of 1,000,000 chats")
    print(f"task layer: {error_budget(0.99, 900_000):,} of 900,000 tasks (30 d)")
    print(f"task layer: {error_budget(0.99, 840_000):,} of 840,000 tasks (28 d)")


def demo_burn_arithmetic():
    print("== burn rate arithmetic")
    burn = burn_rate(72, 1000, 0.995)
    print(f"7.2% failing against a 0.5% budget: burn {burn:.1f}x")
    print(f"budget lasts {days_to_empty(burn):.2f} days")
    print(f"one hour at {burn:.1f}x uses {share_spent(burn, 1):.1%}")
    print(f"a steady 0.8% leak: burn {burn_rate(8, 1000, 0.995):.1f}x, "
          f"empty in {days_to_empty(1.6):.1f} days")


def spike_series(failing_minutes, per_minute=100, bad=8):
    clock = FakeClock()
    series = Series(clock)
    for _ in range(4320):                       # three quiet days
        clock.sleep(60)
        series.record(0, per_minute)
    for _ in range(failing_minutes):
        clock.sleep(60)
        series.record(bad, per_minute)
    return series


def demo_worked_example():
    print("== sale-day spike: 8% of chats failing")
    series = spike_series(55)
    for label, seconds in (("1 h", 3600), ("5 min", 300)):
        bad, total = series.window(seconds)
        print(f"{label:>5} window: {bad:>3} of {total:>5,} failed, "
              f"burn {burn_rate(bad, total, 0.995):.1f}")
    d = alert_decision(series)
    print(f"after 55 minutes: {d.action} "
          f"({d.rule.burn}x over {d.rule.long_s // 60} min "
          f"and {d.rule.short_s // 60} min)")
    print(f"after 54 minutes: {alert_decision(spike_series(54)).action}")


def demo_time_to_alert():
    print("== how long until Relay raises an alert")
    print("failing  burn  first alert             after")
    for rate in (1.0, 0.20, 0.08, 0.04, 0.01, 0.004):
        minute, d = minutes_to_alert(rate)
        burn = rate / 0.005
        if minute is None:
            what, after = "none in 4 days", "-"
        else:
            what = (f"{d.action} ({d.rule.burn:g}x, "
                    f"{d.rule.long_s // 3600} h)"
                    if d.rule.long_s < 86400 else
                    f"{d.action} ({d.rule.burn:g}x, 3 d)")
            after = hours(minute)
        print(f"{rate:>6.1%} {burn:>5.1f}  {what:<22}  {after}")


def demo_blip_and_clear():
    print("== blips, and how fast an alert clears")
    clock = FakeClock()
    series = Series(clock)
    for _ in range(4320):
        clock.sleep(60)
        series.record(0, 100)
    for _ in range(3):
        clock.sleep(60)
        series.record(100, 100)                 # a 3-minute outage
    bad, total = series.window(300)
    print(f"5 min window alone: {bad / total:.0%} failing, would page")
    print(f"decision with both windows: {alert_decision(series).action}")
    for label, rules in (("both windows", RULES),
                         ("the 1 h window alone", long_window_only())):
        first, cleared = minutes_to_clear(rules)
        print(f"with {label}: fires at minute {first}, "
              f"quiet {cleared} min after the fix")


def demo_sheet(tasks):
    print("== the SLO sheet, one illustrative 28 days")
    secs = [t.seconds for t in tasks]
    success = 100 * sum(t.resolved for t in tasks) / len(tasks)
    measured = {
        "availability": 99.81, "first token within 2 s": 96.8,
        "first-pass validity": 98.6, "answers judged good": 91.0,
        "refusals": 1.4, "cost per success": 0.031,
        "task success": round(success, 1),
        "judge pass, weekly": 90.8,
        "p95 task latency": round(percentile(secs, 95), 1),
        "cost per resolved task": round(cost_per_resolved(tasks), 3),
    }
    results = check_sheet(measured)
    for slo, value, ok in results:
        print(line(slo, value, ok))
    return results, share_within(secs, 8)


def demo_health():
    print("== shallow and deep checks")
    deps = [
        Dependency("model endpoint", True, "READY", "READY"),
        Dependency("tracking API", True, "", "out for delivery"),
        Dependency("policy index", True, "no results", "14 days"),
        Dependency("memory store", True, "last order PP-1", "PP-1"),
    ]
    print("dependency      shallow  deep")
    for row in health_table(deps):
        print(row)


def demo_policy():
    print("== budget policy")
    for left in (0.80, 0.40, 0.20, 0.0):
        print(f"{left:>4.0%} left: {policy_rung(left)}")


def demo_report(results, within):
    print("== one-page report")
    notes = {"p95 task latency": f"only {within:.0%} of tasks finished "
             "within 8 seconds; we promised 95%."}
    spends = [Spend(1200, True, "cheaper-model trial, 14 September"),
              Spend(700, False, "provider timeouts, 21 September")]
    for text in render_report("28 days to 4 October 2026", results, 5000,
                              spends, notes):
        print(text)


def main():
    tasks = demo_tasks()
    demo_percentiles()
    demo_quality()
    results, within = demo_sheet(tasks)
    demo_budget()
    demo_burn_arithmetic()
    demo_worked_example()
    demo_time_to_alert()
    demo_blip_and_clear()
    demo_health()
    demo_policy()
    demo_report(results, within)


if __name__ == "__main__":
    main()
