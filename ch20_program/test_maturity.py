"""Tests for the maturity placement."""
from ch20_program import relay_data as rd
from ch20_program.maturity import CONTROLS, LEVELS, place


def names(*levels):
    return {n for lv in levels for n, _ in CONTROLS[lv]}


def test_nothing_in_place_is_level_zero_and_names_level_one():
    level, missing = place(set())
    assert level == 0 and LEVELS[level] == "Vibes"
    assert [n for n, _ in missing] == [n for n, _ in CONTROLS[1]]


def test_each_level_needs_all_of_its_controls():
    assert place(names(1))[0] == 1
    assert place(names(1, 2))[0] == 2
    assert place(names(1, 2, 3))[0] == 3
    assert place(names(1, 2, 3, 4)) == (4, [])


def test_one_missing_control_holds_the_level_down():
    have = names(1, 2, 3) - {"traces"}
    assert place(have) == (2, [("traces", 11)])


def test_the_ladder_is_not_a_menu():
    # a team with every level 3 and 4 control and no level 1 is level 0
    assert place(names(2, 3, 4))[0] == 0


def test_tools_bought_do_not_move_the_level():
    level, missing = place(rd.TOOL_HEAVY)
    assert level == 0 and len(rd.TOOL_HEAVY_BOUGHT) == 4
    assert missing == [("validated output", 2),
                       ("tool tiers and contracts", 2),
                       ("idempotent writes", 2)]


def test_relay_today_is_operated_and_one_control_from_governed():
    assert place(rd.RELAY_HAS) == (
        3, [("scoped credentials and review line", 18)])


def test_every_control_names_a_chapter_that_exists():
    for group in CONTROLS.values():
        assert all(1 <= ch <= 20 for _, ch in group)
    assert sum(len(g) for g in CONTROLS.values()) == 16
    assert len(LEVELS) == 5
