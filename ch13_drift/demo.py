"""Every Chapter 13 output.   python3 -m ch13_drift.demo"""
import random
from datetime import date

from ch08_rag.corpus import DOCS
from ch08_rag.lifecycle import freshness_alarm
from ch13_drift.alerts import (ALERT_LOG, fortnight_false_alarms,
                               group_incidents, median_alert_days, review,
                               route)
from ch13_drift.bands import (check_rate, false_alarm_rate, first_alert,
                              noise_band, rate_band)
from ch13_drift.online import judged_by_segment
from ch13_drift.probe import (ALIAS, CASES, EXPERT, flipped_topics,
                              judge_band, judged_rate, monthly_kappa,
                              rerun_judge, run_probe, snapshot_behind)
from ch13_drift.rag_drift import drift_table, make_index
from ch13_drift.relay_sim import (ACTION_TOOLS, BASE_MIX, SEGMENTS,
                                  SIGNALS, TOOLS, input_chars, tool_calls,
                                  weekly_decay, week_of_conversations)
from ch13_drift.shift import (check_segment, chi2_sf, chi_square,
                              ks_p_value, ks_statistic, psi,
                              psi_noise_floor, shares, tool_shares)


def pct(x):
    return f"{100 * x:.1f}"


def pval(p):
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def peq(p):
    return "p < 0.0001" if p < 0.0001 else f"p = {p:.4f}"


def show_bands():
    for n in (100, 2500):
        lo, hi = rate_band(0.8, n)
        se = (hi - lo) / 4
        print(f"80% good, {n:,} answers: SE {100 * se:.1f} points, "
              f"band {pct(lo)} to {pct(hi)}")
    rates = weekly_decay(34)
    lo, hi = rate_band(0.91, 1000)
    print(f"1,000 answers at 91%: band {pct(lo)} to {pct(hi)}")
    out = [not lo <= r <= hi for r in rates]
    first = out.index(True)
    print(f"weeks 1 to {first}: inside; week {first + 1}: "
          f"{pct(rates[first])} below, week {first + 2}: "
          f"{pct(rates[first + 1])} below")
    alert = first_alert([r < lo for r in rates], 2) + 1
    print(f"alert on week {alert}: two windows in a row")
    for k in (1, 2):
        rate = false_alarm_rate(0.91, 1000, 16, k)
        print(f"clean 16 weeks, {k} below to alert: "
              f"false alarm in {100 * rate:.1f}% of 10,000 runs")
    lo, hi = rate_band(0.81, 30000)
    plain, wide = fortnight_false_alarms()
    print(f"clean fortnights at 30,000 a day, days 1 point apart: "
          f"band {pct(lo)} to {pct(hi)} alerts in {100 * plain:.0f}%, "
          f"band from 28 past days in {100 * wide:.0f}%")


def show_segments():
    counts, queue = judged_by_segment(week_of_conversations(2))
    print("segment       judged  good  rate  band          verdict")
    total = good = 0
    for seg in SEGMENTS:
        n, g = counts[seg.name]
        lo, hi = rate_band(seg.base_good, n)
        print(f"{seg.name:<12} {n:>7} {g:>5} {pct(g / n):>5}  "
              f"{pct(lo):>5} to {pct(hi):>4}  "
              f"{check_rate(seg.base_good, g, n)}")
        total, good = total + n, good + g
    base = sum(s.share * s.base_good for s in SEGMENTS)
    lo, hi = rate_band(base, total)
    print(f"{'all':<12} {total:>7} {good:>5} {pct(good / total):>5}  "
          f"{pct(lo):>5} to {pct(hi):>4}  "
          f"{check_rate(base, good, total)}")
    eu = sum(1 for seg, _ in queue if seg == "EU email")
    print(f"failed answers in the review queue: {len(queue)} "
          f"(EU email: {eu})")


def show_shift():
    print("segment      calls   PSI  verdict   chi-square  p-value")
    for seg in SEGMENTS:
        base, now = tool_calls(seg)
        score, word = check_segment(base, now, TOOLS)
        stat, df = chi_square(base, now, TOOLS)
        print(f"{seg.name:<12} {len(now):>5} {score:>5.2f}  {word:<8}"
              f"{stat:>9.1f}   {pval(chi2_sf(stat, df))}")
    base, now = tool_calls(SEGMENTS[-1])
    stat, _ = chi_square(base, now, TOOLS)
    scaled = psi(shares(base, TOOLS), shares(now, TOOLS)) / (
        1 / len(base) + 1 / len(now))
    print(f"EU email: chi-square {stat:.1f}; "
          f"PSI / (1/n_base + 1/n_now) = {scaled:.1f}")
    for seg in (SEGMENTS[1], SEGMENTS[0]):
        base_s, now_s = tool_calls(seg)
        score = psi(shares(base_s, TOOLS), shares(now_s, TOOLS))
        for tool, (before, after, word) in tool_shares(
                base_s, now_s, ACTION_TOOLS).items():
            if word != "inside":
                print(f"{seg.name}, PSI {score:.2f}: {tool} "
                      f"{pct(before)}% to {pct(after)}%, {word} its band")
    jump = [0.37 if t == "reschedule_delivery" else s * 0.63 / 0.82
            for t, s in zip(TOOLS, BASE_MIX)]
    print(f"reschedule_delivery 18% to 37%, the rest shrunk to fit: "
          f"PSI {psi(BASE_MIX, jump):.2f}")
    floor = psi_noise_floor(len(TOOLS), len(base), 140)
    print(f"noise floor, 5 tools, 140 calls: PSI {floor:.3f}")
    print(check_segment(base[:3000], now[:140], TOOLS)[1])
    rng = random.Random(1)
    for n, mix in ((200_000, (0.415, 0.303, 0.18, 0.03, 0.072)),
                   (60, (0.22, 0.40, 0.15, 0.03, 0.20))):
        a = rng.choices(TOOLS, (0.42, 0.30, 0.18, 0.03, 0.07), k=n)
        b = rng.choices(TOOLS, mix, k=n)
        score = psi(shares(a, TOOLS), shares(b, TOOLS))
        stat, df = chi_square(a, b, TOOLS)
        print(f"{n:,} calls a side: PSI {score:.4f}, "
              f"chi-square {peq(chi2_sf(stat, df))}")


def show_lengths():
    rng = random.Random(8)
    before = input_chars(420, 6000, rng)
    for label, median in (("unchanged week", 420), ("customs week", 560)):
        now = input_chars(median, 1500, rng)
        gap = ks_statistic(before, now)
        p = ks_p_value(gap, len(before), len(now))
        print(f"{label}: D {gap:.2f}, {peq(p)}")


def show_probe():
    rng = random.Random(11)
    runs = [run_probe("a-large-v1", rng)[0] for _ in range(10)]
    lo, hi = noise_band(runs, floor=1 / len(CASES))   # at least one case
    hi = min(hi, 1.0)
    print(f"A/A band, 10 runs of a-large-v1: {lo:.2f} to {hi:.2f}")
    rng = random.Random(1)
    alias, pinned, failed = [], [], {"alias": [], "pinned": []}
    for day in range(1, 22):
        a, fa = run_probe(snapshot_behind(ALIAS, day, 15), rng)
        p, fp = run_probe(snapshot_behind("a-large-v1", day, 15), rng)
        alias.append(a)
        pinned.append(p)
        failed["alias"].append(fa)
        failed["pinned"].append(fp)
    print("day  alias  pinned")
    for day in range(14, 17):
        flag = "  <- alias below band" if alias[day - 1] < lo else ""
        print(f"{day:>3}   {alias[day - 1]:.2f}    {pinned[day - 1]:.2f}"
              f"{flag}")
    alert = first_alert([v < lo for v in alias], 2) + 1
    stray = sum(v < lo for v in pinned)
    never = first_alert([v < lo for v in pinned], 2) is None
    print(f"alias alert on day {alert}; pinned: {stray} stray days, "
          f"two in a row: {'never' if never else 'yes'}")
    before = [c for day in failed["alias"][7:14] for c in day]
    after = [c for day in failed["alias"][14:21] for c in day]
    topic = dict(CASES)
    flips = flipped_topics(before, after)
    parts = [f"{t} {sum(topic[c] == t for c in before)} to "
             f"{sum(topic[c] == t for c in after)}"
             for t, more in sorted(flips.items(), key=lambda kv: -kv[1])
             if more >= 3]
    print("failures in 7 days, before then after:")
    print("  " + ", ".join(parts[:2]))
    print("  " + ", ".join(parts[2:]))


def show_judge():
    lo, hi = judge_band(10)
    print(f"judge kappa band, 10 re-runs on the held-out set: "
          f"{lo:.2f} to {hi:.2f}")
    kappas = monthly_kappa(5, 5)
    print("months 1 to 4: kappa " + ", ".join(f"{k:.2f}"
                                              for k in kappas[:4])
          + ", all inside")
    print(f"month 5: kappa {kappas[4]:.2f} "
          f"{'below' if kappas[4] < lo else 'inside'}")
    again = rerun_judge(0.93, 0.70, random.Random(99))
    from ch05_judge.agreement import cohen_kappa
    print(f"re-run at once: kappa {cohen_kappa(again, EXPERT):.2f}")
    before = judged_rate(0.75, 0.93, 0.92)
    after = judged_rate(0.75, 0.93, 0.70)
    print(f"judged good rate, true 75%: "
          f"{pct(before)} before, {pct(after)} after")


def show_rag():
    index = make_index()
    quiet = freshness_alarm(index, DOCS, date(2026, 10, 4))
    print(f"Chapter 8's freshness alarm: {len(quiet)} alerts")
    rows, (lo, hi), alert = drift_table(index)
    print(f"zero-result band from weeks 1 to 4: {pct(lo)} to {pct(hi)}")
    print("weeks 1 to 4: " + ", ".join(pct(r[2]) + "%" for r in rows[:4]))
    print("week  customs  zero-result  pages-read PSI")
    for week, share, zero, flag, score in rows[4:]:
        mark = "  above band" if flag else ""
        print(f"{week:>4}  {100 * share:>5.0f}%  {pct(zero):>10}%  "
              f"{score:>13.2f}{mark}")
    print(f"alert on week {alert}")


def show_alerts():
    print("signal                    kind     alert on day (median)")
    found = median_alert_days()
    for sig in SIGNALS:
        day, runs = found[sig.name]
        print(f"{sig.name:<25} {sig.kind:<8} {day:>4.0f}   "
              f"({runs} of 500 runs)")
    cases = [("refund share up, 2 windows", True, True),
             ("refund share up, 1 window", True, False),
             ("one segment's good rate down, 2 days", False, True),
             ("answer length up, 1 window", False, False)]
    for label, money, held in cases:
        print(f"{label}: {route(money, held)}")
    hours = [(1, "EU email"), (1, "EU email"), (2, "EU email"),
             (2, "EU chat"), (3, "EU email"), (3, "EU chat"),
             (4, "EU email"), (9, "web chat"), (30, "EU email")]
    groups = group_incidents(hours)
    print(f"{len(hours)} alerts in 30 hours: {len(groups)} incidents")
    print("rule                        route  fired  acted  precision")
    for rule, where, fired, acted, prec, verdict in review(ALERT_LOG):
        print(f"{rule:<27} {where:<6} {fired:>5} {acted:>6} {prec:>9.2f}"
              f"  {verdict}")


def main():
    for part in (show_bands, show_segments, show_shift, show_lengths,
                 show_probe, show_judge, show_rag, show_alerts):
        part()
        print()


if __name__ == "__main__":
    main()
