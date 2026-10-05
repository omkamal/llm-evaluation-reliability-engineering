"""Tests for the readiness scorecard."""
from datetime import date

from ch20_program import relay_data as rd
from ch20_program.readiness import QUESTIONS, Answer, review, standing

TODAY = date(2026, 10, 5)
FRESH = "2026-10-01"


def all_yes(**changes):
    answers = {q.key: Answer("yes", FRESH) for q in QUESTIONS}
    answers.update(changes)
    return answers


def test_all_fresh_yes_is_launch():
    assert review(QUESTIONS, all_yes(), TODAY) == ("launch", [])


def test_a_named_risk_on_a_non_blocker_is_launch_with_named_risks():
    risky = Answer("partly", FRESH, "cost budget covers chat only",
                   "Sam", 14)
    verdict, why = review(QUESTIONS, all_yes(cost=risky), TODAY)
    assert verdict == "launch with named risks"
    assert why == ["cost: partly; cost budget covers chat only; "
                   "Sam, 14 days"]


def test_a_risk_without_an_owner_or_a_date_is_not_named():
    for gap in (Answer("partly", FRESH, "", "Sam", 14),
                Answer("partly", FRESH, "r", "", 14),
                Answer("partly", FRESH, "r", "Sam", 0)):
        verdict, why = review(QUESTIONS, all_yes(cost=gap), TODAY)
        assert verdict == "not yet"
        assert why == ["cost: partly; the risk has no name, owner "
                       "or date"]


def test_a_blocker_must_be_a_fresh_yes():
    named = Answer("partly", FRESH, "r", "Sam", 14)
    verdict, why = review(QUESTIONS, all_yes(kill=named), TODAY)
    assert (verdict, why) == ("not yet", ["kill: partly"])


def test_a_no_stops_even_a_non_blocker():
    verdict, why = review(QUESTIONS, all_yes(creds=Answer("no", FRESH)),
                          TODAY)
    assert (verdict, why) == ("not yet", ["creds: no"])


def test_a_missing_answer_is_a_no():
    answers = all_yes()
    del answers["trace"]
    assert review(QUESTIONS, answers, TODAY) == (
        "not yet", ["trace: no, no answer"])


def test_old_evidence_turns_a_yes_into_a_partly():
    assert standing(Answer("yes", "2026-07-07"), TODAY) == ("yes", "")
    assert standing(Answer("yes", "2026-07-06"), TODAY) == (
        "partly", "evidence is 91 days old")


def test_a_stale_blocker_stops_the_launch():
    old = Answer("yes", "2026-05-01", "r", "Priya", 14)
    verdict, why = review(QUESTIONS, all_yes(gate=old), TODAY)
    assert verdict == "not yet"
    assert why == ["gate: partly, evidence is 157 days old"]


def test_three_blockers_in_the_question_list():
    assert [q.key for q in QUESTIONS if q.blocker] == [
        "gate", "guard", "kill"]
    assert len(QUESTIONS) == 11


def test_the_eve_of_inc6_is_not_yet_for_exactly_the_four_gaps():
    verdict, why = review(QUESTIONS, rd.EVE_OF_INC6, date(2026, 9, 9))
    assert verdict == "not yet"
    assert why == ["guard: no", "creds: no", "review: no", "kill: no"]


def test_today_is_launch_with_three_named_risks():
    verdict, why = review(QUESTIONS, rd.NOW, TODAY)
    assert verdict == "launch with named risks"
    assert [w.split(":")[0] for w in why] == [
        "failover", "creds", "runbooks"]
    assert why[0].startswith("failover: partly, evidence is 144 days old")


def test_closing_the_three_risks_gives_launch():
    fixed = dict(rd.NOW)
    fixed["failover"] = Answer("yes", "2026-10-05")
    fixed["creds"] = Answer("yes", "2026-10-05")
    fixed["runbooks"] = Answer("yes", "2026-10-05")
    assert review(QUESTIONS, fixed, TODAY) == ("launch", [])


def test_exercise_two_risks_closed_one_left():
    fixed = dict(rd.NOW)
    fixed["failover"] = Answer("yes", "2026-10-05")
    fixed["creds"] = Answer("yes", "2026-10-05")
    verdict, why = review(QUESTIONS, fixed, TODAY)
    assert verdict == "launch with named risks"
    assert why == ["runbooks: partly; three page alerts reach no sound "
                   "runbook; Priya, 14 days"]
