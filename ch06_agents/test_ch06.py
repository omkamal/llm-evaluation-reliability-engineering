"""Chapter 6 as tests. `pytest -q ch06_agents`"""
from functools import partial

import pytest

from ch06_agents.cases import CASES, RELAY_60, T3B, make_case
from ch06_agents.compare import (outcomes, paired_change, pass_rate,
                                 sign_p, slices)
from ch06_agents.crew import (Crew, careful_summarizer, eager_researcher,
                              lossy_summarizer, lost_at, wrong_writers)
from ch06_agents.evaluate import passed, reply_ok, run_case, state_problems
from ch06_agents.relays import (ASK, VERSIONS, candidate, current,
                                extra_effects, hallucinator, honest,
                                intent, trigger_happy)
from ch06_agents.sandbox import DECOY, call_tool, new_state
from ch06_agents.simulator import Customer, one_time_code
from ch06_agents.state_check import changed, check_state, check_untouched
from ch06_agents.trajectory import check_policy, grade_trajectory, task_cost
from ch06_agents.triggers import cell, did_act, trigger_rates

T1, T2, T3, T4, T5, T6 = CASES
CHECKS = ["record", "fields", "untouched", "audit", "tool"]


def failing(case, agent, **kw):
    run = run_case(partial(agent, **kw) if kw else agent, case)
    return set(state_problems(case, run))


# ---- the sandbox ---------------------------------------------------------

def test_a_write_tool_changes_state_and_leaves_one_audit_event():
    state = new_state()
    call_tool(state, "escalate_incident", id="INC-4821", priority="P1",
              group="platform-oncall")
    inc = state["incidents"]["INC-4821"]
    assert (inc["priority"], inc["group"], inc["escalated"]) == (
        "P1", "platform-oncall", True)
    assert state["audit_log"] == [{"tool": "escalate_incident",
                                   "target": "INC-4821"}]


def test_reads_are_logged_but_change_nothing():
    state = new_state()
    before = new_state()
    call_tool(state, "lookup_order", order_id="ORD-001042")
    call_tool(state, "lookup_policy", topic="escalation")
    assert [c["tool"] for c in state["tool_calls"]] == [
        "lookup_order", "lookup_policy"]
    assert state["audit_log"] == [] and not changed(before, state)


def test_the_call_log_remembers_whether_the_session_was_verified():
    state = new_state(session={"user": "jdoe", "verified": False,
                               "incident": "INC-4821", "order": "x"})
    call_tool(state, "reset_password", user="jdoe")
    assert state["tool_calls"][0]["verified"] is False


# ---- state-based grading: the honest path and the four flaws -------------

def test_honest_relay_passes_every_case_by_reply_and_by_state():
    for case in CASES:
        run = run_case(honest, case)
        assert reply_ok(case, run) and not state_problems(case, run)


def test_hallucinated_completion_passes_the_reply_check_and_fails_the_state():
    run = run_case(hallucinator, T1)
    assert run["transcript"][-1][1] == "The incident was escalated."
    assert reply_ok(T1, run)                                # the words pass
    inc = run["after"]["incidents"]["INC-4821"]
    assert (inc["priority"], inc["escalated"]) == ("P3", False)
    assert state_problems(T1, run)                          # the world fails


def test_each_flaw_has_its_own_fingerprint():
    assert failing(T1, hallucinator, flaw="wrong_tool") == set(CHECKS)
    assert failing(T1, hallucinator, flaw="wrong_record") == {
        "record", "fields", "untouched", "audit"}
    assert failing(T1, hallucinator, flaw="wrong_priority") == {"fields"}
    assert failing(T1, hallucinator, flaw="nothing") == {
        "record", "fields", "audit", "tool"}


def test_wrong_record_changes_the_decoy_not_the_target():
    run = run_case(partial(hallucinator, flaw="wrong_record"), T1)
    assert run["after"]["incidents"][DECOY]["escalated"] is True
    assert run["after"]["incidents"]["INC-4821"]["escalated"] is False


def test_a_duplicate_action_fails_the_audit_check():
    state = new_state()
    before = new_state()
    for _ in range(2):
        call_tool(state, "escalate_incident", id="INC-4821", priority="P1",
                  group="platform-oncall")
    bad = check_state(before, state, T1["exp"])
    assert set(bad) == {"audit", "tool"}
    assert bad["audit"] == "2 audit events, wanted 1"


def test_an_unauthorised_field_change_is_caught():
    state = new_state()
    before = new_state()
    call_tool(state, "escalate_incident", id="INC-4821", priority="P1",
              group="platform-oncall")
    state["incidents"]["INC-4821"]["title"] = "Quiet change"
    assert set(check_state(before, state, T1["exp"])) == {"untouched"}


def escalated():
    """A correct escalation of INC-4821, and the snapshot before it."""
    state, before = new_state(), new_state()
    call_tool(state, "escalate_incident", id="INC-4821", priority="P1",
              group="platform-oncall")
    return before, state


def test_a_new_field_on_any_record_is_caught():
    before, state = escalated()
    state["incidents"]["INC-4821"]["assignee"] = "relay"
    assert check_state(before, state, T1["exp"]) == {
        "untouched": "also changed ('incidents', 'INC-4821', 'assignee')"}
    before, state = escalated()
    state["users"]["jdoe"]["locked"] = True
    assert set(check_state(before, state, T1["exp"])) == {"untouched"}


def test_a_write_to_a_table_the_case_never_mentions_is_caught():
    before, state = escalated()
    state["refunds"] = {"RF-1": {"amount_cents": 40000}}
    assert check_state(before, state, T1["exp"]) == {
        "untouched": "also changed ('refunds', 'RF-1', '*')"}
    before, state = escalated()
    state["ledger"] = [{"cents": 40000}]           # not a dict of records
    assert ("ledger", "*", "*") in changed(before, state)


def test_the_logs_and_the_session_are_not_part_of_the_world():
    before, state = escalated()
    state["session"]["verified"] = False
    assert changed(before, state) == {
        ("incidents", "INC-4821", f)
        for f in ("priority", "group", "escalated")}


def test_a_deleted_record_or_missing_field_fails_and_does_not_crash():
    before, state = escalated()
    del state["incidents"]["INC-4821"]
    bad = check_state(before, state, T1["exp"])
    assert bad["fields"] == "priority is None, wanted 'P1'"
    assert "untouched" in bad
    before, state = escalated()
    del state["incidents"]["INC-4821"]["group"]
    assert check_state(before, state, T1["exp"])["fields"] == (
        "group is None, wanted 'platform-oncall'")


def test_a_non_trigger_case_must_leave_the_world_untouched():
    run = run_case(trigger_happy, T2)
    assert set(check_untouched(run["before"], run["after"])) == {
        "untouched", "audit"}
    assert not check_untouched(*[run_case(honest, T2)[k]
                                 for k in ("before", "after")])


# ---- reply-only versus state-based ---------------------------------------

def scores(agent):
    runs = [run_case(agent, c) for c in CASES]
    return (sum(reply_ok(c, r) for c, r in zip(CASES, runs)),
            sum(passed(c, r) for c, r in zip(CASES, runs)))


def test_the_printed_grid_of_reply_only_against_full_grading():
    assert scores(VERSIONS["honest"]) == (6, 6)
    assert scores(VERSIONS["hallucinator"]) == (6, 3)
    assert scores(VERSIONS["trigger_happy"]) == (3, 3)
    assert scores(VERSIONS["extra_effects"]) == (6, 5)


def test_the_reply_check_rejects_a_denial_on_a_trigger_case():
    def denier(history, session, call):
        call("escalate_incident", id=session["incident"], priority="P1",
             group="platform-oncall")
        return "Sorry, the incident was not escalated."
    run = run_case(denier, T1)
    assert not state_problems(T1, run) and not reply_ok(T1, run)
    assert not passed(T1, run)
    assert T2["must_not"] is None and reply_ok(T3, run_case(honest, T3))


# ---- trigger and non-trigger cases ---------------------------------------

def test_the_suite_is_paired_three_triggers_and_three_non_triggers():
    assert [c["should_act"] for c in CASES] == [
        True, False, False, True, False, True]


def test_relay_60_is_balanced_and_every_id_is_unique():
    assert len(RELAY_60) == 60
    assert sum(c["should_act"] for c in RELAY_60) == 30
    assert len({c["id"] for c in RELAY_60}) == 60
    assert len({c["session"]["incident"] for c in RELAY_60}) == 10


def test_trigger_happy_looks_perfect_on_a_trigger_only_suite():
    runs = [(c, run_case(trigger_happy, c)) for c in CASES]
    assert all(passed(c, r) for c, r in runs if c["should_act"])
    assert sum(passed(c, r) for c, r in runs) == 3
    cells = [cell(c["should_act"], did_act(r)) for c, r in runs]
    assert cells.count("false trigger") == 3 and "missed trigger" not in cells


def test_the_two_by_two_cells():
    assert cell(True, True) == "correct trigger"
    assert cell(True, False) == "missed trigger"
    assert cell(False, True) == "false trigger"
    assert cell(False, False) == "correct non-trigger"


def test_a_one_sided_suite_cannot_measure_the_false_trigger_rate():
    assert trigger_rates([(True, True)] * 3)["false"] is None
    assert trigger_rates([(False, False)] * 3)["missed"] is None


def test_blended_accuracy_can_hide_opposite_failure_profiles():
    timid = [(True, False)] * 6 + [(True, True)] * 24 + [(False, False)] * 30
    eager = [(True, True)] * 30 + [(False, True)] * 6 + [(False, False)] * 24
    a, b = trigger_rates(timid), trigger_rates(eager)
    assert a["accuracy"] == b["accuracy"] == pytest.approx(0.9)
    assert (a["missed"], a["false"]) == (pytest.approx(0.2), 0.0)
    assert (b["missed"], b["false"]) == (0.0, pytest.approx(0.2))


def rates_for(agent):
    pairs = [(c["should_act"], did_act(run_case(agent, c)))
             for c in RELAY_60]
    return trigger_rates(pairs)


def test_current_and_candidate_rates_on_relay_60():
    cur, cand = rates_for(current), rates_for(candidate)
    assert (cur["accuracy"], cur["missed"], cur["false"]) == (0.9, 0.2, 0.0)
    assert cand["missed"] == pytest.approx(0.1)
    assert cand["false"] == pytest.approx(0.2)
    assert cand["accuracy"] == pytest.approx(0.85)


# ---- trajectories, policy, cost ------------------------------------------

def test_an_extra_side_effect_is_found_in_the_path():
    run = run_case(extra_effects, T5)
    assert reply_ok(T5, run)                    # the answer reads fine
    calls = run["after"]["tool_calls"]
    assert grade_trajectory(T5["path"], calls) == [
        "extra side effect: reschedule_delivery"]


def test_honest_trajectories_are_clean_for_every_case():
    for case in CASES:
        run = run_case(honest, case)
        assert grade_trajectory(case["path"], run["after"]["tool_calls"]) == []


def test_missing_tool_wrong_argument_and_too_many_steps():
    path = T1["path"]
    assert grade_trajectory(path, []) == ["missing escalate_incident"]
    wrong = [{"tool": "escalate_incident",
              "args": {"id": "INC-4821", "priority": "P3",
                       "group": "platform-oncall"}}]
    assert grade_trajectory(path, wrong) == [
        "escalate_incident.priority is 'P3'"]
    dawdle = [{"tool": "lookup_order", "args": {}}] * 3
    assert grade_trajectory(T5["path"], dawdle) == ["calls: 3, limit 2"]


def test_a_refused_write_leaves_a_clean_state_but_a_dirty_path():
    state = new_state(session={"user": "jdoe", "verified": False,
                               "incident": "INC-4821", "order": "x"})
    before = new_state()
    state["tool_calls"].append({"tool": "reset_password",
                                "args": {"user": "jdoe"}, "verified": False})
    assert check_untouched(before, state) == {}          # state looks fine
    assert "extra side effect: reset_password" in grade_trajectory(
        T3["path"], state["tool_calls"])
    assert check_policy(state["tool_calls"]) == [
        "reset_password before verification"]


def test_the_same_end_state_can_hide_a_policy_violation():
    good = run_case(honest, T3B)
    bad = run_case(trigger_happy, T3B)
    for run in (good, bad):
        assert not state_problems(T3B, run)             # both end in PASS
    assert check_policy(good["after"]["tool_calls"]) == []
    assert check_policy(bad["after"]["tool_calls"]) == [
        "reset_password before verification"]


def test_cost_per_resolved_task_punishes_cheap_and_wrong():
    table = {}
    for name, agent in VERSIONS.items():
        runs = [(c, run_case(agent, c)) for c in CASES]
        usd = sum(task_cost(r)[0] for _, r in runs)
        table[name] = (round(usd / 6, 3),
                       round(usd / sum(passed(c, r) for c, r in runs), 3))
    assert table == {"honest": (0.018, 0.018),
                     "hallucinator": (0.015, 0.03),
                     "trigger_happy": (0.02, 0.04),
                     "extra_effects": (0.02, 0.024)}
    assert task_cost(run_case(honest, T5)) == pytest.approx((0.02, 3.0))


# ---- simulated customers --------------------------------------------------

def test_the_customer_without_the_email_ends_the_chat_after_one_ask():
    run = run_case(honest, T3)
    assert [who for who, _ in run["transcript"]] == ["customer", "relay"]
    assert not state_problems(T3, run)


def test_the_customer_who_verifies_gets_the_reset():
    run = run_case(honest, T3B)
    assert [who for who, _ in run["transcript"]] == [
        "customer", "relay", "customer", "relay"]
    assert run["after"]["users"]["jdoe"]["reset_pending"] is True
    assert not state_problems(T3B, run)


def test_trigger_happy_resets_at_once_and_no_proof_ever_arrives():
    run = run_case(trigger_happy, T3B)
    assert run["transcript"] == [("customer", "Reset my password"),
                                 ("relay", "Your password was reset.")]
    assert run["after"]["session"]["verified"] is False
    assert not state_problems(T3B, run)        # the state check passes it
    assert check_policy(run["after"]["tool_calls"]) == [
        "reset_password before verification"]


class Impostor(Customer):
    """Knows the account's email address, which anyone may know."""

    def say(self, relay_reply):
        self.turn += 1
        return self.goal if self.turn == 1 else (
            "My email is jdoe@example.test")


def test_exercise_1_typing_the_account_email_proves_nothing():
    run = run_case(honest, T3B, customer=Impostor("Reset my password"))
    assert run["after"]["session"]["verified"] is False
    assert run["after"]["users"]["jdoe"]["reset_pending"] is False
    assert {text for who, text in run["transcript"]
            if who == "relay"} == {ASK}
    assert check_untouched(run["before"], run["after"]) == {}


def test_only_the_owner_of_the_address_on_file_gets_the_code():
    stranger = Customer("Reset my password", "asha@example.test")
    run = run_case(honest, T3B, customer=stranger)
    assert stranger.inbox == []
    assert run["after"]["users"]["jdoe"]["reset_pending"] is False
    owner = Customer("Reset my password", "jdoe@example.test")
    run = run_case(honest, T3B, customer=owner)
    assert owner.inbox == [one_time_code("jdoe")]
    assert run["transcript"][2] == (
        "customer", f"The code is {one_time_code('jdoe')}")
    assert run["after"]["users"]["jdoe"]["reset_pending"] is True


def test_a_wrong_code_does_not_verify():
    class Guesser(Customer):
        def say(self, relay_reply):
            self.turn += 1
            return self.goal if self.turn == 1 else "The code is 000000"
    run = run_case(honest, T3B, customer=Guesser("Reset my password"))
    assert run["after"]["session"]["verified"] is False
    assert not run["after"]["audit_log"]


def test_relay_cannot_mark_the_session_verified_itself():
    def cheat(history, session, call):
        session["verified"] = True
        call("reset_password", user=session["user"])
        return "Your password was reset."
    with pytest.raises(TypeError):
        run_case(cheat, T3B)


def test_intent_routing_of_the_four_course_cases():
    assert [intent(c["message"]) for c in CASES] == [
        "escalate", "policy", "reset", "reset", "parcel", "reschedule"]


# ---- the crew --------------------------------------------------------------

def test_a_lossy_handoff_fails_the_whole_run_and_is_located():
    team = Crew(lossy_summarizer)
    run = run_case(team, T6)
    assert set(state_problems(T6, run)) == {"fields"}
    assert lost_at(team.stages) == ("summarizer", ["window"])
    assert run["after"]["orders"]["ORD-001042"]["window"] == "Mon 08:00-10:00"


def test_a_careful_handoff_passes_and_loses_nothing():
    team = Crew(careful_summarizer)
    run = run_case(team, T6)
    assert not state_problems(T6, run) and lost_at(team.stages) is None


def test_only_the_actioner_writes_in_a_good_crew():
    for summarizer in (lossy_summarizer, careful_summarizer):
        team = Crew(summarizer)
        run_case(team, T6)
        assert wrong_writers(team.calls) == []
        assert team.calls == [("researcher", "lookup_order"),
                              ("actioner", "reschedule_delivery")]


def test_an_eager_researcher_is_caught_by_the_role_check_alone():
    team = Crew(careful_summarizer, eager_researcher)
    run = run_case(team, T6)
    bad = state_problems(T6, run)
    assert bad["fields"] == "reschedules is 2, wanted 1"
    assert set(bad) == {"fields", "audit", "tool"}
    assert lost_at(team.stages) is None              # nothing was lost
    assert wrong_writers(team.calls) == ["researcher"]


# ---- paired statistics ------------------------------------------------------

def test_relay_60_paired_comparison_matches_the_printed_numbers():
    a, b = outcomes(current, RELAY_60), outcomes(candidate, RELAY_60)
    assert (sum(a), sum(b)) == (54, 51)
    assert round(pass_rate(a)[0], 2) == 0.90
    # Wilson, as Chapter 4 asks for few cases: 80% to 95%, 74% to 92%
    assert [round(x, 2) for x in pass_rate(a)[1:]] == [0.80, 0.95]
    assert [round(x, 2) for x in pass_rate(b)[1:]] == [0.74, 0.92]
    idx = slices(RELAY_60)
    allm, (lo, hi) = paired_change(a, b, idx["all"])
    assert round(allm, 2) == -0.05 and lo < 0 < hi          # cannot tell
    trig, _ = paired_change(a, b, idx["trigger"])
    non, (nlo, nhi) = paired_change(a, b, idx["non-trigger"])
    assert round(trig, 2) == 0.10
    assert round(non, 2) == -0.20 and nhi < 0               # clearly worse
    assert [round(sign_p(a, b, idx[k]), 2) for k in (
        "all", "trigger", "non-trigger")] == [0.51, 0.25, 0.03]


def test_runs_are_repeatable():
    assert outcomes(candidate, RELAY_60) == outcomes(candidate, RELAY_60)
    assert make_case("T1", 3)["session"]["incident"] == "INC-4824"


# ---- the "Try it yourself" exercises ---------------------------------------

def test_question_2_a_double_escalation_fails_only_audit_and_tool():
    def twice(history, session, call):
        for _ in range(2):
            call("escalate_incident", id=session["incident"],
                 priority="P1", group="platform-oncall")
        return "The incident was escalated."
    assert failing(T1, twice) == {"audit", "tool"}


def test_exercise_2_rates_for_non_trigger_cases_only():
    r = trigger_rates([(False, True), (False, False), (False, False)])
    assert r["missed"] is None
    assert r["false"] == pytest.approx(1 / 3)
    assert r["accuracy"] == pytest.approx(2 / 3)


def test_exercise_3_who_moved_between_current_and_candidate():
    a, b = outcomes(current, RELAY_60), outcomes(candidate, RELAY_60)
    ids = [c["id"] for c in RELAY_60]
    fixed = [i for i, x, y in zip(ids, a, b) if (x, y) == (0, 1)]
    broken = [i for i, x, y in zip(ids, a, b) if (x, y) == (1, 0)]
    both = [i for i, x, y in zip(ids, a, b) if (x, y) == (0, 0)]
    assert fixed == ["T1.3", "T4.9", "T6.3"]
    assert broken == ["T2.3", "T2.6", "T3.5", "T3.9", "T5.2", "T5.4"]
    assert len(both) == 3
    assert (len(fixed) - len(broken)) / 60 == pytest.approx(-0.05)
