"""Tests for the pager-load report."""
from datetime import date, datetime

from ch13_drift.alerts import ALERT_LOG
from ch20_program import relay_data as rd
from ch20_program.pager import (Caps, Page, days_on_call, on_call,
                                person_flags, rest_owed, rule_flags,
                                rule_stats, shift_of, shifts_by_person)

MON = date(2026, 9, 7)


def at(day, hhmm):
    return datetime.fromisoformat(f"{day}T{hhmm}")


def test_shift_boundaries():
    assert shift_of(at("2026-09-08", "08:00")) == (date(2026, 9, 8), "day")
    assert shift_of(at("2026-09-08", "19:59")) == (date(2026, 9, 8), "day")
    assert shift_of(at("2026-09-08", "20:00")) == (date(2026, 9, 8),
                                                   "night")
    assert shift_of(at("2026-09-09", "07:59")) == (date(2026, 9, 8),
                                                   "night")
    assert shift_of(at("2026-09-09", "00:00")) == (date(2026, 9, 8),
                                                   "night")


def test_a_night_after_midnight_belongs_to_the_week_it_started_in():
    # Sunday night's 02:00 page is the first week's person, not the next
    assert on_call(rd.ROTA, MON, date(2026, 9, 13)) == "Priya"
    page = Page(at("2026-09-14", "02:00"), "r", False)
    assert shifts_by_person([page], rd.ROTA, MON) == {
        "Priya": {(date(2026, 9, 13), "night"): 1}}


def test_the_rota_repeats_weekly():
    assert [on_call(rd.ROTA, MON, date(2026, 9, d))
            for d in (7, 14, 21, 28)] == ["Priya", "Sam", "Priya", "Sam"]


def test_the_pages_agree_with_chapter_13s_month():
    stats = rule_stats(rd.PAGES)
    wanted = {rule: (fired, acted)
              for rule, where, fired, acted in ALERT_LOG
              if where == "page"}
    assert stats == wanted and len(rd.PAGES) == 13


def test_everything_is_on_or_before_the_books_now():
    assert max(p.when.date() for p in rd.PAGES) <= rd.TODAY
    assert min(p.when.date() for p in rd.PAGES) >= MON


def test_load_per_person():
    mine = shifts_by_person(rd.PAGES, rd.ROTA, MON)
    assert sum(mine["Priya"].values()) == 7
    assert sum(mine["Sam"].values()) == 6
    night = lambda who: sum(n for (_, k), n in mine[who].items()
                            if k == "night")
    assert (night("Priya"), night("Sam")) == (5, 4)
    assert max(mine["Priya"].values()) == 4
    assert max(mine["Sam"].values()) == 2        # at the cap, not over


def test_the_three_person_flags():
    assert person_flags(rd.PAGES, rd.ROTA, MON, rd.MONTH_DAYS) == [
        "Priya: 4 pages in the night shift of 23 Sep (cap 2)",
        "Priya: on call 50% of days (cap 25%)",
        "Sam: on call 50% of days (cap 25%)"]


def test_rest_is_owed_after_the_bad_night_only():
    assert rest_owed(rd.PAGES, rd.ROTA, MON) == [
        ("Priya", date(2026, 9, 24))]


def test_four_on_the_rota_sit_exactly_at_the_cap():
    four = ("Priya", "Sam", "Ines", "Lena")
    assert days_on_call(four, MON, 28) == dict.fromkeys(four, 7)
    flags = person_flags([], four, MON, 28)
    assert flags == []                       # 25% is not over 25%


def test_the_rule_that_cries_wolf_is_flagged_and_the_good_one_is_not():
    assert rule_flags(rd.PAGES) == [
        "rule 'good rate down, 1 window': 11/13 pages, "
        "2 acted on, precision 0.18"]


def test_a_rule_at_the_bar_or_with_too_few_pages_is_not_flagged():
    def pages(n, acted):
        return [Page(at("2026-09-08", "10:00"), "r", i < acted)
                for i in range(n)]
    assert rule_flags(pages(4, 2)) == []            # precision 0.5
    assert rule_flags(pages(2, 0)) == []            # under min_pages
    assert len(rule_flags(pages(4, 1))) == 1        # 0.25


def test_tightening_the_noisy_rule_clears_the_page_cap():
    kept = [p for p in rd.PAGES if p.rule != rd.ONE_WINDOW]
    assert len(kept) == 2
    assert person_flags(kept, ("Priya", "Sam", "Ines", "Lena"), MON,
                        28) == []
    assert rule_flags(kept) == [] and rest_owed(kept, rd.ROTA, MON) == []


def test_a_looser_cap_changes_the_flags():
    loose = Caps(per_shift=4, on_call_share=0.5)
    assert person_flags(rd.PAGES, rd.ROTA, MON, 28, loose) == []


def test_exercise_a_rota_of_three():
    three = ("Priya", "Sam", "Ines")
    month = days_on_call(three, MON, 28)
    assert month == {"Priya": 14, "Sam": 7, "Ines": 7}   # 4 weeks, 3 people
    cycle = days_on_call(three, MON, 84)                 # whole cycles
    assert set(cycle.values()) == {28} and 28 / 84 > 0.25


def test_sam_away_leaves_priya_on_call_every_day():
    assert days_on_call(("Priya",), MON, 21) == {"Priya": 21}
