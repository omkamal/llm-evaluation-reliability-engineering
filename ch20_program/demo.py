"""Every Chapter 20 output.   python3 -m ch20_program.demo"""
from datetime import date
from textwrap import fill

from ch20_program import relay_data as rd
from ch20_program.findings import (closed_share, mix, overdue,
                                   without_case)
from ch20_program.maturity import CONTROLS, LEVELS, place
from ch20_program.owners import accountable_load, check, single_hands
from ch20_program.pager import (days_on_call, person_flags, rest_owed,
                                rule_flags, rule_stats,
                                shifts_by_person)
from ch20_program.readiness import QUESTIONS, review
from ch20_program.report import Line, expected_loss_avoided, render
from ch20_program.runbooks import audit


def demo_owners():
    print("== one accountable name per item")
    for label, sheet in (("before", rd.BEFORE), ("after", rd.AFTER)):
        found = check(sheet, rd.ROSTER)
        print(f"{label}: {len(found) or 'no'} problems")
        for problem in found:
            print(f"  {problem}")
        hands = len(single_hands(sheet, rd.ROSTER))
        away = len(single_hands(sheet, rd.ROSTER, count_away=False))
        print(f"  one pair of hands: {hands} of {len(sheet)}, "
              f"{away} with Sam away")
    load = accountable_load(rd.AFTER)
    print("answers for: " + ", ".join(
        f"{who} {n}" for who, n in sorted(load.items())))


def demo_pager():
    print("== the month's pager load")
    pages, rota, start = rd.PAGES, rd.ROTA, rd.ROTA_START
    mine = shifts_by_person(pages, rota, start)
    days = days_on_call(rota, start, rd.MONTH_DAYS)
    print(f"{'':<7}{'days':>5}{'pages':>7}{'night':>7}{'busiest':>9}")
    for who in rota:
        shifts = mine[who]
        night = sum(n for (_, kind), n in shifts.items()
                    if kind == "night")
        print(f"{who:<7}{days[who]:>5}{sum(shifts.values()):>7}"
              f"{night:>7}{max(shifts.values()):>9}")
    for flag in person_flags(pages, rota, start, rd.MONTH_DAYS):
        print(flag)
    for who, day in rest_owed(pages, rota, start):
        print(f"rest owed to {who}: {day:%d %b}")
    for flag in rule_flags(pages):
        print(flag)
    kept = [p for p in pages if p.rule != rd.ONE_WINDOW]
    print(f"without that rule: {len(kept)} pages in {rd.MONTH_DAYS} days")
    four = days_on_call(("Priya", "Sam", "Ines", "Lena"), start,
                        rd.MONTH_DAYS)
    print(f"four on the rota: {max(four.values())} of {rd.MONTH_DAYS} "
          "days each")


def demo_runbooks():
    print("== runbook audit")
    found, sound, total = audit(rd.PAGE_ALERTS, rd.RUNBOOKS, rd.TODAY)
    for line in found:
        print(line)
    print(f"page alerts with a sound runbook: {sound} of {total}")


def demo_readiness():
    print("== readiness reviews")
    for label, day, answers in (
            ("eve of INC-6", date(2026, 9, 9), rd.EVE_OF_INC6),
            ("today", rd.TODAY, rd.NOW)):
        verdict, reasons = review(QUESTIONS, answers, day, rd.ROSTER)
        print(f"{label}: {verdict}")
        for why in reasons:
            print(fill(why, 64, initial_indent="  ",
                       subsequent_indent="    "))


def demo_maturity():
    print("== placing a feature on the ladder")
    for label, have in (("tool-heavy team", rd.TOOL_HEAVY),
                        ("Relay today", rd.RELAY_HAS)):
        level, missing = place(have)
        total = sum(len(group) for group in CONTROLS.values())
        print(f"{label}: level {level} ({LEVELS[level]}), "
              f"{len(have)} of {total} controls")
        for name, ch in missing:
            print(f"  next: {name} (Chapter {ch})")


def demo_findings():
    print("== the learning review")
    f = rd.FINDINGS
    print("findings: " + ", ".join(f"{n} {k}" for k, n in mix(f).items()))
    print(f"closed: {sum(x.done for x in f)} of {len(f)} "
          f"({closed_share(f):.0%})")
    for item, late in overdue(f, rd.TODAY):
        print(f"overdue {late} days: {item.text} ({item.owner})")
    for item in without_case(f):
        print(f"no lasting check: {item.text}")


def demo_report():
    print("== the quarterly report")
    pages = rd.PAGES
    night = sum(1 for p in pages if p.when.hour >= 20 or p.when.hour < 8)
    hours = len(pages) * 0.5
    spend, saved = expected_loss_avoided(1000, 0.02, 400, 1.50)
    _, low = expected_loss_avoided(1000, 0.008, 400, 1.50)
    _, high = expected_loss_avoided(1000, 0.05, 400, 1.50)
    sections = [
        ("What it costs", [
            Line("Cost per resolved task: $0.028, promised under $0.06.",
                 "measured"),
            Line(f"Pages: {len(pages)}, {night} at night, for two people "
                 "on call half the time.", "measured"),
            Line(f"Time on them: {hours:.1f} engineer-hours, at 30 minutes "
                 "a page.", "assumed")]),
        ("What it protects", [
            Line("Promises kept: 9 of 10.", "measured"),
            Line("INC-6: found after 38 minutes, contained 30 minutes "
                 "later.", "measured"),
            Line("If it came back: 7 minutes open, not 68. Declared in 5 "
                 "and the 2-minute runbook.", "assumed"),
            Line(f"Reviewing 1,000 large credits costs ${spend:,.0f} "
                 f"and avoids up to ${saved:,.0f} of expected loss at a "
                 f"2% error rate (${low:,.0f} to ${high:,.0f} at 0.8% "
                 "to 5%), if every review catches the error.",
                 "assumed")]),
        ("What we still carry", [
            Line("Findings closed: 6 of 8. Open: scoped credentials, a "
                 "dead runbook link. Three named risks, each with an "
                 "owner and a date.", "measured")]),
        ("What we need from you", [
            Line("A decision: two more people on the rota, so that "
                 "nobody carries the pager more than a quarter of "
                 "the days.", "measured")]),
    ]
    for text in render("Relay program report, 28 days to 4 October 2026",
                       sections):
        print(text)


def main():
    demo_owners()
    demo_pager()
    demo_runbooks()
    demo_readiness()
    demo_maturity()
    demo_findings()
    demo_report()


if __name__ == "__main__":
    main()
