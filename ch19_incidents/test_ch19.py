"""Tests for Chapter 19. Every worked example in the text is asserted."""
from datetime import date

import pytest

from ch06_agents.sandbox import new_state, ord_id
from common.clock import FakeClock
from ch19_incidents import compensate as comp
from ch19_incidents.comms import StatusUpdate, lint
from ch19_incidents.declare import (Incident, declare_reasons, response,
                                    severity)
from ch19_incidents.demo import inc6_clock
from ch19_incidents.flags import (CURRENT, LAST_GOOD, SAFE, FlagStore,
                                  resolve)
from ch19_incidents.postmortem import (ActionItem, Factor, Postmortem,
                                       cases_added, closed_share,
                                       problems)
from ch19_incidents.recovery import can_close, settled
from ch19_incidents.runbook import (INC6_RUNBOOK, NotALadder, Step, climb,
                                    check_ladder)
from ch19_incidents.standin import (NOTE_CASES, attempt,
                                    credit_under_limit_works, harm_probe)
from ch19_incidents.timeline import (at, clock_text, durations, merge,
                                     render, Scribe)


def store(**flags):
    return FlagStore({"bundle": CURRENT, **flags})


# ---- the clock ------------------------------------------------------

def test_clock_text_round_trips():
    assert clock_text(at("14:02")) == "14:02"
    assert clock_text(at("00:00")) == "00:00"


def test_inc6_clock_matches_the_incident_facts():
    rows, marks = inc6_clock()
    assert [clock_text(r[0]) for r in rows] == [
        "14:02", "14:03", "14:40", "14:52", "15:10"]
    assert durations(marks) == {"detect": 38, "harm open": 49,
                                "first brake": 12, "contain": 30,
                                "message to pin": 68}


def test_trace_rows_leave_free_text_out():
    rows, _ = inc6_clock()
    text = " ".join(r[2] for r in rows)
    assert "amount_cents=40000" in text and "reason" not in text


def test_merge_orders_by_time_and_render_prints_one_line_each():
    clock = FakeClock(at("10:00"))
    scribe = Scribe(clock)
    clock.t = at("10:05")
    scribe.note("second")
    clock.t = at("10:01")
    scribe.note("first")
    lines = render(merge(scribe.rows))
    assert [x.split()[-1] for x in lines] == ["first", "second"]


# ---- the flags ------------------------------------------------------

def test_normal_state_is_the_full_belt():
    cfg = resolve(store())
    assert cfg.mode == "normal" and len(cfg.tools) == 8
    assert cfg.bundle == CURRENT and not cfg.approval


def test_disable_a_tool_removes_only_that_tool():
    cfg = resolve(store(disabled_tools=("issue_refund",)))
    assert "issue_refund" not in cfg.tools and len(cfg.tools) == 7


def test_approval_keeps_the_tool_but_asks_first():
    cfg = resolve(store(approval_for=("issue_refund",)))
    assert "issue_refund" in cfg.tools
    assert cfg.approval == {"issue_refund"}


def test_approval_for_a_disabled_tool_is_dropped():
    cfg = resolve(store(approval_for=("issue_refund",),
                        disabled_tools=("issue_refund",)))
    assert not cfg.approval


def test_degrade_to_tier_two_keeps_only_reads():
    cfg = resolve(store(max_tier=2))
    assert cfg.tools == {"lookup_order", "lookup_policy"}


def test_kill_switch_is_read_first_and_runs_no_tool():
    cfg = resolve(store(kill_switch=True, max_tier=1))
    assert cfg.mode == "handoff" and not cfg.tools


def test_pin_chooses_the_bundle():
    assert resolve(store(bundle=LAST_GOOD)).bundle == LAST_GOOD


def test_unread_flag_with_service_down_gets_the_safe_default():
    cold = store(kill_switch=True)
    cold.reachable = False
    cfg = resolve(cold)
    assert cfg.bundle == SAFE["bundle"] == LAST_GOOD
    assert cfg.mode == "normal"


def test_service_down_keeps_the_last_value_read():
    live = store(kill_switch=True)
    assert resolve(live).mode == "handoff"
    live.reachable = False
    assert resolve(live).mode == "handoff"


def test_every_flip_is_logged_with_who_and_why():
    flags = FlagStore(clock=FakeClock(5.0))
    flags.set("kill_switch", True, "Sam", "INC-6")
    assert flags.changes == [(5.0, "Sam", "kill_switch", True, "INC-6")]


# ---- the probe and the ladder --------------------------------------

def test_normal_state_leaves_every_planted_note_case_open():
    assert harm_probe(resolve(store())) == ["INJ-01", "INJ-02", "INJ-03"]


def test_each_rung_alone():
    left = {name: harm_probe(resolve(store(**extra))) for name, extra in (
        ("tool", {"disabled_tools": ("issue_refund",)}),
        ("approve", {"approval_for": ("issue_refund",)}),
        ("degrade", {"max_tier": 2}),
        ("pin", {"bundle": LAST_GOOD}),
        ("kill", {"kill_switch": True}))}
    assert left["tool"] == left["approve"] == ["INJ-02", "INJ-03"]
    assert left["degrade"] == left["pin"] == left["kill"] == []


def test_approval_queues_instead_of_acting():
    cfg = resolve(store(approval_for=("issue_refund",)))
    assert attempt(cfg, NOTE_CASES[0]) == "queued"


def test_runbook_climbs_to_the_first_clean_rung():
    clock = FakeClock(at("14:40"))
    flags = store()
    lines = []
    done = climb(INC6_RUNBOOK, flags, harm_probe, clock, "Sam",
                 log=lines.append)
    assert done.rung == 3
    assert lines == [
        "14:41 rung 1 disable issue_refund: INJ-02, INJ-03 still open",
        "14:42 rung 3 pin bundle 2026.08.25: clean"]
    assert resolve(flags).bundle == LAST_GOOD
    assert not flags.get("kill_switch")       # never climbed higher


def test_runbook_stops_at_the_first_rung_when_it_is_enough():
    clock = FakeClock(at("14:40"))
    only_credit = lambda cfg: ([] if "issue_refund" not in cfg.tools
                               else ["INJ-01"])
    done = climb(INC6_RUNBOOK, store(), only_credit, clock, "Sam",
                 log=lambda _: None)
    assert done.rung == 1 and clock.now() == at("14:41")


def test_runbook_returns_none_when_even_the_top_rung_leaves_harm():
    clock = FakeClock(at("14:40"))
    done = climb(INC6_RUNBOOK, store(), lambda cfg: ["X"], clock, "Sam",
                 log=lambda _: None)
    assert done is None


def test_a_runbook_must_be_a_ladder():
    with pytest.raises(NotALadder):
        check_ladder([Step(4, "kill", "kill_switch", True),
                      Step(1, "tool", "disabled_tools", ("x",))])
    check_ladder([Step(1, "a", "f", 1), Step(1, "b", "f", 2)])


# ---- declare, severity, roles ---------------------------------------

def test_declare_reasons():
    assert declare_reasons(irreversible_action=True)
    assert declare_reasons(minutes_unsolved=30) == []
    assert declare_reasons(minutes_unsolved=60)
    assert len(declare_reasons(customers_hurt=True,
                               other_team_needed=True)) == 2


def test_severity_follows_what_the_agent_did():
    assert severity(irreversible=True) == 1
    assert severity(data_exposed=True) == 1
    assert severity(broad=True, customers_notice=True) == 2
    assert severity(broad=True) == 3          # nobody notices: not SEV 2
    assert severity() == 3


def test_response_words():
    assert "5 min" in response(1) and "30 min" in response(1)
    assert "ticket" in response(3)


def test_incident_roles_are_kept_apart():
    team = Incident("INC-6", 1, "14:40", "Priya", "Sam", "Marcus", "Lena")
    assert team.problems() == []
    team.ops = "Priya"
    assert team.problems() == ["commander is also changing the system"]
    team.ops, team.comms = "Sam", "Sam"
    assert len(team.problems()) == 1


# ---- compensating actions ------------------------------------------

def books(spent=0):
    state = comp.open_ledger(
        new_state(0), {ord_id(0): "cust-17", ord_id(1): "cust-22"}, {})
    credit = comp.issue_refund(state, ord_id(1), 40000, "k1")
    if spent:
        comp.spend(state, "cust-22", spent, "s1")
    return state, credit


def test_unspent_credit_is_taken_back_in_full():
    state, credit = books()
    assert comp.reverse_credit(state, credit, "r1") == {
        "recovered": 40000, "owed": 0}
    assert comp.balance(state, "cust-22") == 0


def test_spent_credit_is_recovered_in_part_and_the_rest_is_owed():
    state, credit = books(spent=15000)
    assert comp.reverse_credit(state, credit, "r1") == {
        "recovered": 25000, "owed": 15000}
    assert comp.balance(state, "cust-22") == 0      # owed is a claim


def test_the_ledger_is_append_only():
    state, credit = books(spent=15000)
    before = [dict(x) for x in state["ledger"]]
    comp.reverse_credit(state, credit, "r1")
    assert state["ledger"][:len(before)] == before


def test_reversal_with_the_same_key_posts_nothing_new():
    state, credit = books(spent=15000)
    first = comp.reverse_credit(state, credit, "r1")
    lines, audit = len(state["ledger"]), len(state["audit_log"])
    assert comp.reverse_credit(state, credit, "r1") == first
    assert (len(state["ledger"]), len(state["audit_log"])) == (lines,
                                                              audit)


def test_one_audit_event_per_write():
    state, credit = books()
    comp.reverse_credit(state, credit, "r1")
    assert [e["tool"] for e in state["audit_log"]] == [
        "issue_refund", "reverse_credit"]


def test_a_second_credit_with_the_same_key_pays_once():
    state, credit = books()
    assert comp.issue_refund(state, ord_id(1), 40000, "k1") == credit
    assert comp.balance(state, "cust-22") == 40000


# ---- verifying recovery --------------------------------------------

def suite():
    out = {n["id"]: (lambda c, n=n: attempt(c, n) != "done")
           for n in NOTE_CASES}
    out["own credit under $50"] = credit_under_limit_works
    return out


def test_containment_is_not_recovery():
    cfg = resolve(store(bundle=LAST_GOOD,
                        disabled_tools=("issue_refund",)))
    ok, why = can_close(cfg, suite(), {})
    assert not ok and why == ["own credit under $50 fails"]


def test_the_old_bundle_with_credits_on_closes_the_suite_too():
    ok, _ = can_close(resolve(store(bundle=LAST_GOOD)), suite(), {})
    assert ok


def test_the_vulnerable_bundle_fails_the_planted_note_cases():
    ok, why = can_close(resolve(store()), suite(), {})
    assert not ok and len(why) == 3


def test_settled_needs_k_windows_inside_the_band():
    # band for 3% on 1,000 tasks is 1.9% to 4.1%
    assert not settled(0.03, [(0, 1000), (24, 1000)])
    assert settled(0.03, [(0, 1000), (24, 1000), (29, 1000)])
    assert not settled(0.03, [(29, 1000)])             # one window only
    assert not settled(0.03, [(1, 20), (1, 20)])       # too little data


def test_a_silent_signal_is_below_its_band_not_healthy():
    cfg = resolve(store(bundle="2026.09.17"))
    ok, why = can_close(cfg, suite(), {"credit share": (
        0.03, [(0, 1000), (0, 1000)])})
    assert not ok and why == ["credit share out of band"]


def test_closing_walks_through_four_windows():
    cfg = resolve(store(bundle="2026.09.17"))
    credits = [0, 24, 29, 31]
    handoffs = [310, 150, 128, 121]
    closed = []
    for w in range(1, 5):
        ok, _ = can_close(cfg, suite(), {
            "credit share": (0.03, [(c, 1000) for c in credits[:w]]),
            "hand-off share": (0.12, [(h, 1000) for h in handoffs[:w]])})
        closed.append(ok)
    assert closed == [False, False, False, True]


# ---- communications ------------------------------------------------

GOOD = StatusUpdate("A $400 credit went to the wrong account at 14:03.",
                    "One account.", "Credits are switched off.", "15:15")


def test_a_good_update_has_four_parts_and_a_clean_lint():
    assert GOOD.text().count("\n") == 3
    assert lint(GOOD, "internal") == []


def test_lint_flags_each_thing_not_to_say():
    bad = StatusUpdate(
        "We believe a prompt change by Sam was probably the cause.",
        "All customers.", "This will be fixed by 15:00.", "")
    assert lint(bad, "customer", people=("Sam",)) == [
        "no time for the next update", "guesses at the cause",
        "promises a fix time", "points at a person",
        "internal words: prompt"]


def test_internal_words_are_fine_inside_the_team():
    inside = StatusUpdate("The prompt bundle was pinned.", "None.",
                          "Checking the flag.", "15:30")
    assert lint(inside, "internal") == []
    assert lint(inside, "customer")


def test_done_is_not_said_before_recovery_is_verified():
    done = StatusUpdate("It is now resolved.", "None.", "Nothing.",
                        "16:00")
    assert lint(done, "internal") == ["says fixed before recovery is "
                                      "verified"]
    assert lint(done, "internal", verified=True) == []


def test_long_lines_are_wrapped():
    long = StatusUpdate("word " * 40, "x", "y", "z")
    assert all(len(line) <= 70 for line in long.text().splitlines())


# ---- the postmortem record ----------------------------------------

def inc6():
    pm = Postmortem("INC-6", "2026-09-10", factors=[
        Factor("prevent", "no ownership check on a credit"),
        Factor("detect", "Finance noticed, no alert on credits"),
        Factor("contain", "no kill switch, no version pin")])
    pm.actions = [
        ActionItem("ownership check", "Sam", "2026-09-17", "G-OWN-01",
                   True),
        ActionItem("note family into the suite", "Priya", "2026-09-15",
                   "INJ-01 INJ-02 INJ-03", True),
        ActionItem("kill switch and pin, drilled", "Priya", "2026-09-22",
                   "D-KILL-01", True),
        ActionItem("page on credits outside band", "Priya", "2026-09-24",
                   "A-CRED-01", True),
        ActionItem("scoped credentials", "Lena", "2026-10-02",
                   "G-SCOPE-01", False)]
    return pm


TODAY = date(2026, 10, 4)


def test_inc6_record_has_one_overdue_item_and_nothing_else():
    assert problems(inc6(), TODAY) == [
        "'scoped credentials': overdue"]


def test_postmortem_numbers():
    pm = inc6()
    assert closed_share(pm) == 0.8
    assert cases_added(pm) == 7


def test_an_item_needs_owner_date_and_case():
    pm = inc6()
    pm.actions = [ActionItem("be more careful")]
    assert problems(pm, TODAY) == [
        "'be more careful': no owner", "'be more careful': no date",
        "'be more careful': no regression case"]


def test_a_date_before_the_incident_is_flagged():
    pm = inc6()
    pm.actions[0].due = "2026-09-01"
    assert "'ownership check': due before the incident" in problems(
        pm, TODAY)


def test_a_missing_phase_is_flagged():
    pm = inc6()
    pm.factors = pm.factors[:1]
    assert [p for p in problems(pm, TODAY) if "factor" in p] == [
        "no contributing factor about 'detect'",
        "no contributing factor about 'contain'"]


def test_factors_may_not_name_a_person_but_owners_may():
    pm = inc6()
    pm.factors[0].text = "Sam shipped the prompt"
    found = problems(pm, TODAY, people=("Sam",))
    assert found == ["'Sam shipped the prompt': names a person",
                     "'scoped credentials': overdue"]


# ---- the chapter's exercises ----------------------------------------

def test_exercise_spent_in_full():
    state, credit = books(spent=40000)
    assert comp.reverse_credit(state, credit, "r1") == {
        "recovered": 0, "owed": 40000}


def test_exercise_noisy_window():
    credits = [0, 24, 45, 31, 30]
    settled_after = [w for w in range(1, 6)
                     if settled(0.03, [(c, 1000) for c in credits[:w]])]
    assert settled_after == [5]


def test_exercise_the_one_rung():
    settings = {"tool": {"disabled_tools": ("issue_refund",)},
                "approve": {"approval_for": ("issue_refund",)},
                "degrade": {"max_tier": 2},
                "pin": {"bundle": LAST_GOOD},
                "kill": {"kill_switch": True}}
    both = [name for name, extra in settings.items()
            if not harm_probe(resolve(store(**extra)))
            and credit_under_limit_works(resolve(store(**extra)))]
    assert both == ["pin"]
