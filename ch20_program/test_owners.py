"""Tests for the ownership check (RACI) and the roster."""
from ch20_program import relay_data as rd
from ch20_program.owners import (Item, Person, accountable_load, check,
                                 rows, single_hands)

ROSTER = (Person("Ana"), Person("Bo"), Person("Cy", left="2026-08-14"),
          Person("Di", away=True, deputy="Ana"), Person("Ed", away=True))


def sheet(**kw):
    return [Item("thing", kw.get("r", ("Ana", "Bo")),
                 kw.get("a", ("Ana",)))]


def test_a_sound_sheet_has_no_problems():
    assert check(sheet(), ROSTER) == []


def test_zero_accountable_is_a_problem():
    assert check(sheet(a=()), ROSTER) == [
        "thing: accountable is nobody (need exactly one)"]


def test_two_accountable_is_a_problem():
    assert check(sheet(a=("Ana", "Bo")), ROSTER) == [
        "thing: accountable is Ana, Bo (need exactly one)"]


def test_an_owner_who_left_is_a_problem_once():
    # Cy is both responsible and accountable: one message, not two
    found = check(sheet(r=("Cy",), a=("Cy",)), ROSTER)
    assert found == ["thing: Cy left on 2026-08-14"]


def test_a_responsible_person_who_left_is_a_problem():
    assert check(sheet(r=("Ana", "Cy")), ROSTER) == [
        "thing: Cy left on 2026-08-14"]


def test_a_name_not_on_the_roster_is_a_problem():
    assert check(sheet(r=("Ana", "Zed")), ROSTER) == [
        "thing: Zed is not on the roster"]


def test_away_needs_a_deputy_only_for_the_accountable_person():
    assert check(sheet(a=("Di",)), ROSTER) == []
    assert check(sheet(a=("Ed",)), ROSTER) == [
        "thing: Ed is away, no deputy"]
    assert check(sheet(r=("Ana", "Ed")), ROSTER) == []


def test_single_hands_ignores_leavers_not_holidays():
    items = [Item("one", ("Ana",), ("Ana",)),
             Item("gone", ("Ana", "Cy"), ("Ana",)),
             Item("two", ("Ana", "Ed"), ("Ana",))]
    assert single_hands(items, ROSTER) == ["one", "gone"]


def test_the_sheet_before_has_the_three_problems_in_the_text():
    assert check(rd.BEFORE, rd.ROSTER) == [
        "policy index: Jonas left on 2026-08-14",
        "runbook and kill switch: accountable is Priya, Sam "
        "(need exactly one)",
        "postmortem actions: accountable is nobody (need exactly one)"]
    assert len(single_hands(rd.BEFORE, rd.ROSTER)) == 9


def test_the_sheet_after_is_sound_and_spread():
    assert check(rd.AFTER, rd.ROSTER) == []
    assert single_hands(rd.AFTER, rd.ROSTER) == []
    assert all(len(i.accountable) == 1 for i in rd.AFTER)
    assert accountable_load(rd.AFTER) == {
        "Sam": 2, "Priya": 3, "Marcus": 2, "Lena": 3}


def test_the_table_in_the_chapter_is_the_data():
    table = rows(rd.AFTER)
    assert len(table) == 10
    assert table[0] == ("prompts and tool schemas", "Sam, Ines", "Sam",
                        "Priya", "Marcus")
    assert table[8] == ("runbook and kill switch", "Priya, Ines",
                        "Priya", "Sam", "Marcus")


def test_exercise_lena_leaves():
    roster = tuple(Person(p.name, left="2026-10-01") if p.name == "Lena"
                   else p for p in rd.ROSTER)
    found = check(rd.AFTER, roster)
    assert [f.split(":")[0] for f in found] == [
        "tool contracts and tiers", "red-team set", "credentials",
        "postmortem actions"]
    assert single_hands(rd.AFTER, roster) == [
        "tool contracts and tiers", "postmortem actions"]


def test_a_holiday_puts_items_back_in_one_pair_of_hands():
    items = [Item("two", ("Ana", "Di"), ("Ana",))]
    assert single_hands(items, ROSTER) == []
    assert single_hands(items, ROSTER, count_away=False) == ["two"]
    # the repaired sheet survives a resignation, not yet Sam's holiday
    away = single_hands(rd.AFTER, rd.ROSTER, count_away=False)
    assert len(away) == 8
    assert "runbook and kill switch" not in away
    assert len(single_hands(rd.BEFORE, rd.ROSTER, count_away=False)) == 10
