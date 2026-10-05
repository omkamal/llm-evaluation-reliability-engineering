"""Chapter 5 as tests. `pytest -q ch05_judge`"""
from dataclasses import replace

import pytest
from pydantic import ValidationError

from ch04_numbers.stats import paired_bootstrap
from ch05_judge.agreement import (chance_agreement, cohen_kappa, confusion,
                                  labels_from_matrix, landis_koch,
                                  observed_agreement, tpr_tnr)
from ch05_judge.answers import (expert_label, friday_tweak, make_answers,
                                pad, twin)
from ch05_judge.calibrate import (JudgeCard, calibrate, judge_labels,
                                  kappa_interval, meets_bar, split)
from ch05_judge.fixes import (length_gap, self_preference_gap, swapped,
                              swap_consistency, tally, winner)
from ch05_judge.jury import aggregate, needs_a_person
from ch05_judge.production import (MixedJudges, ScoreRecord,
                                   monthly_judge_cost, pass_rate)
from ch05_judge.simjudge import (JudgeConfig, Temperament, compare, reply,
                                 score_of)
from ch05_judge.verdict import (ANCHORS, RUBRIC, Verdict, build_prompt,
                                grade, verdict_gateway)

B = Temperament("b")
V1 = JudgeConfig("v1", B)
V2 = JudgeConfig("v2", B, anchored=True, evidence_first=True,
                 few_shot=True, style_note=True)
HONEST = Temperament("h", lean=0, first=0, long=0, kin=0, charm=0,
                     wobble=0, signal=1.0)


# ---- the structured verdict -------------------------------------------
def test_a_valid_verdict_parses_and_evidence_comes_first():
    v = Verdict.model_validate_json(
        '{"evidence": "Cites 14 days.", "score": 5, "verdict": "pass"}')
    assert v.score == 5 and v.verdict == "pass"
    assert list(Verdict.model_fields) == ["evidence", "score", "verdict"]


@pytest.mark.parametrize("raw", [
    '{"evidence": "x", "score": 2, "verdict": "pass"}',     # contradiction
    '{"evidence": "x", "score": 4, "verdict": "fail"}',
    '{"evidence": "x", "score": 11, "verdict": "pass"}',    # off the scale
    '{"evidence": "", "score": 4, "verdict": "pass"}',      # no evidence
    '{"evidence": "x", "score": 4, "verdict": "pass", "tone": "kind"}',
    '{"score": 4, "verdict": "pass"}',                      # missing field
])
def test_a_malformed_verdict_is_refused(raw):
    with pytest.raises(ValidationError):
        Verdict.model_validate_json(raw)


def test_the_gateway_quarantines_a_contradiction_with_the_judge_version():
    gw = verdict_gateway()
    bad = '{"evidence": "Looks fine.", "score": 2, "verdict": "pass"}'
    assert gw.check(bad, prompt_version="v2", model_version="judge") is None
    q = gw.quarantine[0]
    assert q.errors[0][1] == "value_error" and q.prompt_version == "v2"


def test_the_prompt_has_four_parts_in_order_and_anchors_1_3_5():
    p = build_prompt("How long?", "14 days.")
    order = [p.index(k) for k in ("TASK", "RUBRIC", "EVIDENCE FIRST",
                                  "REPLY")]
    assert order == sorted(order)
    for level in (1, 3, 5):
        assert f"\n{level}  " in RUBRIC
    assert max(len(line) for line in p.splitlines()) <= 74
    assert set(ANCHORS) == {1, 2, 3, 4, 5}


def test_grade_runs_prompt_call_and_validation_end_to_end():
    a = make_answers(1, 1)[0]
    v = grade(verdict_gateway(), a.question, a,
              lambda prompt: reply(V2, a.question, a))
    assert v is not None and v.verdict in ("pass", "fail")
    assert grade(verdict_gateway(), a.question, a, lambda p: "not json") \
        is None


# ---- the simulated judge ----------------------------------------------
def test_with_every_flaw_switched_off_the_judge_is_exact():
    cfg = JudgeConfig("h", HONEST)
    for a in make_answers(60, 3):
        assert score_of(cfg, a) == a.quality


def test_the_simulation_is_deterministic():
    answers = make_answers(30, 4)
    assert [score_of(V1, a) for a in answers] == \
           [score_of(V1, a) for a in answers]
    assert answers == make_answers(30, 4)
    other = JudgeConfig("v1", replace(B, family="z"))
    assert [score_of(V1, a) for a in answers] != \
           [score_of(other, a) for a in answers]


# ---- leniency, and the Friday tweak -----------------------------------
def test_the_plain_judge_is_lenient_and_the_anchored_one_is_not():
    answers = make_answers(240, 11)
    truth = [expert_label(a) for a in answers]
    plain = judge_labels(V1, answers)
    assert plain.count("pass") > truth.count("pass") + 10
    assert tpr_tnr(plain, truth)[1] < 0.5            # catches few failures
    assert tpr_tnr(judge_labels(V2, answers), truth)[1] > 0.8


def test_the_plain_judge_scores_the_friday_tweak_higher_not_lower():
    old = make_answers(200, 21)
    new = friday_tweak(old, 22)
    assert sum(a.quality >= 4 for a in new) < sum(a.quality >= 4
                                                  for a in old)
    for cfg, sign in ((V1, 1), (V2, -1)):
        a = [score_of(cfg, x) for x in old]
        b = [score_of(cfg, x) for x in new]
        diff, (lo, hi) = paired_bootstrap(a, b, resamples=1000)
        assert sign * diff > 0
        assert (lo > 0) if sign > 0 else (hi < 0)    # interval clears zero


# ---- position bias ----------------------------------------------------
PAIRS = [(a, twin(a)) for a in make_answers(200, 2)]


def test_a_position_biased_judge_favours_whoever_is_listed_first():
    t = tally(V1, PAIRS)
    assert t["x"] > t["y"] + 0.25          # identical answers, unequal wins


def test_the_swap_rule_removes_the_tilt_and_returns_ties():
    t = tally(V1, PAIRS, swap=True)
    assert abs(t["x"] - t["y"]) < 0.12
    assert t["tie"] > tally(V1, PAIRS)["tie"] + 0.3


def test_swapped_needs_both_orders_to_agree():
    good, poor = make_answers(80, 6), make_answers(80, 7)
    first = next(a for a in good if a.quality == 5)
    last = next(a for a in poor if a.quality == 1)
    assert swapped(V2, first, last) == "x"
    assert swapped(V2, last, first) == "y"
    # a judge that only likes the first slot cannot win both orders
    biased = JudgeConfig("p", Temperament("p", lean=0, first=5, long=0,
                                          kin=0, charm=0, wobble=0,
                                          signal=0))
    assert winner(biased, first, last) == "x"
    assert swapped(biased, first, last) == "tie"


def test_examples_in_the_prompt_make_the_judge_more_consistent():
    assert (swap_consistency(replace(V1, few_shot=True), PAIRS)
            > swap_consistency(V1, PAIRS))


def test_compare_is_a_tie_inside_the_margin():
    a = make_answers(1, 1)[0]
    assert compare(JudgeConfig("h", HONEST), a, twin(a)) == "tie"


# ---- verbosity and self-preference ------------------------------------
def test_padding_wins_for_a_plain_judge_and_a_style_note_helps():
    padded = [(a, pad(a)) for a in make_answers(200, 4)]
    plain = tally(V1, padded, swap=True)
    noted = tally(replace(V1, style_note=True), padded, swap=True)
    assert plain["y"] > 0.4 and plain["y"] > plain["x"] + 0.3
    assert noted["y"] < plain["y"] - 0.15


def test_length_gap_shrinks_with_a_style_note():
    answers = make_answers(1000, 3)
    assert length_gap(V1, answers) > 0.2
    assert length_gap(replace(V1, style_note=True), answers) < 0.1


def test_a_judge_favours_its_own_family_and_a_cross_family_judge_does_not():
    relay = make_answers(200, 5, author="a")
    rival = make_answers(200, 5, author="b")
    own = self_preference_gap(JudgeConfig("x", Temperament("a")),
                              relay, rival)
    other = self_preference_gap(JudgeConfig("x", Temperament("b")),
                                relay, rival)
    assert own > 0.2 and other < -0.2      # each leans toward its own


# ---- agreement: the worked examples -----------------------------------
def test_the_200_label_matrix_is_rebuilt_exactly():
    judge, expert = labels_from_matrix(175, 15, 5, 5)
    assert len(judge) == 200
    assert confusion(judge, expert) == (175, 15, 5, 5)
    assert observed_agreement(judge, expert) == 0.90
    assert round(chance_agreement(judge, expert), 2) == 0.86
    assert round(cohen_kappa(judge, expert), 2) == 0.29
    assert landis_koch(cohen_kappa(judge, expert)) == "fair"
    tpr, tnr = tpr_tnr(judge, expert)
    assert round(tpr, 2) == 0.97 and round(tnr, 2) == 0.25


def test_the_kappa_interval_around_029_is_wide():
    judge, expert = labels_from_matrix(175, 15, 5, 5)
    k, (lo, hi) = kappa_interval(judge, expert, resamples=1000)
    assert round(k, 2) == 0.29 and lo < 0.1 and hi > 0.4


def test_kappa_is_one_for_perfect_zero_for_chance_negative_for_opposite():
    a = ["pass", "fail"] * 50
    assert cohen_kappa(a, a) == 1.0
    assert cohen_kappa(a, ["pass"] * 100) == 0.0
    flipped = ["fail" if x == "pass" else "pass" for x in a]
    assert cohen_kappa(a, flipped) == -1.0


def test_landis_koch_words():
    words = {-0.1: "poor", 0.1: "slight", 0.29: "fair", 0.5: "moderate",
             0.7: "substantial", 0.82: "almost perfect"}
    assert {k: landis_koch(k) for k in words} == words


# ---- calibration ------------------------------------------------------
def test_split_is_disjoint_and_covers_everything():
    items = list(range(240))
    dev, test = split(items, seed=1)
    assert set(dev) | set(test) == set(items) and not set(dev) & set(test)
    assert split(items, seed=1) == (dev, test)


def test_calibrating_the_plain_and_the_final_judge():
    dev, test = split(make_answers(240, 11))
    plain, final = calibrate(V1, dev), calibrate(V2, test)
    assert plain["kappa"] < 0.45 and not meets_bar(plain)
    assert final["kappa"] > 0.75 and meets_bar(final)
    assert final["n"] == 120


def test_each_prompt_feature_helps_on_the_dev_set():
    dev, _ = split(make_answers(240, 11))
    cfg, last = V1, calibrate(V1, dev)["kappa"]
    for name in ("anchored", "evidence_first", "style_note"):
        cfg = replace(cfg, **{name: True})
        now = calibrate(cfg, dev)["kappa"]
        assert now > last
        last = now


def test_dropping_the_anchors_makes_a_new_judge_that_fails_the_bar():
    _, test = split(make_answers(240, 11))
    v3 = replace(V2, version="v3", anchored=False)
    assert meets_bar(calibrate(V2, test))
    assert not meets_bar(calibrate(v3, test))


def test_an_unreadable_reply_counts_as_a_fail():
    answers = make_answers(5, 1)
    labels = judge_labels(V2, answers)
    assert len(labels) == 5
    from ch05_judge import calibrate as cal
    broken = cal.grade
    try:
        cal.grade = lambda *a, **k: None
        assert judge_labels(V2, answers) == ["fail"] * 5
    finally:
        cal.grade = broken


def test_the_judge_card_reports_kappa_and_its_interval():
    _, test = split(make_answers(240, 11))
    rep = calibrate(V2, test)
    interval = kappa_interval(judge_labels(V2, test),
                              [expert_label(a) for a in test],
                              resamples=500)[1]
    card = "\n".join(JudgeCard(V2, rep, interval, "the support lead",
                               "2026-10-04").lines())
    assert f"kappa {rep['kappa']:.2f}" in card and "v2" in card
    assert "120 blind cases" in card


# ---- juries -----------------------------------------------------------
def test_pooling_five_four_and_two():
    s = [5, 4, 2]
    assert round(aggregate(s, "mean"), 2) == 3.67
    assert aggregate(s, "median") == 4
    assert aggregate(s, "majority") == "pass"
    assert aggregate(s, "weighted", [0.0, 0.0, 1.0]) == 2.0
    assert aggregate([5, 1, 1], "majority") == "fail"
    with pytest.raises(ValueError):
        aggregate(s, "mode")


def test_the_jury_beats_each_member_and_the_borderline_slice_is_hard():
    crowd = make_answers(300, 31)
    truth = [expert_label(a) for a in crowd]
    full = dict(anchored=True, evidence_first=True, few_shot=True,
                style_note=True)
    jurors = [JudgeConfig(f"j{f}", replace(B, family=f, wobble=1.0), **full)
              for f in "cde"]
    alone = [calibrate(c, crowd)["kappa"] for c in jurors]
    votes = [[score_of(c, a) for c in jurors] for a in crowd]
    majority = [aggregate(v, "majority") for v in votes]
    assert cohen_kappa(majority, truth) > max(alone)
    flagged = [needs_a_person(v) for v in votes]
    hits = [m == t for m, t in zip(majority, truth)]
    hard = [h for h, f in zip(hits, flagged) if f]
    rest = [h for h, f in zip(hits, flagged) if not f]
    assert sum(rest) / len(rest) > sum(hard) / len(hard) + 0.15
    assert sum(rest) / len(rest) > 0.95


# ---- production -------------------------------------------------------
def test_scores_from_two_judge_versions_never_mix():
    ok = [ScoreRecord("t1", "v2", "pass"), ScoreRecord("t2", "v2", "fail")]
    assert pass_rate(ok) == 0.5
    with pytest.raises(MixedJudges):
        pass_rate(ok + [ScoreRecord("t3", "v1", "pass")])


def test_the_monthly_judge_cost_example():
    judged, cost = monthly_judge_cost(900_000, 0.05, 1500, 150, 1.0, 4.0)
    assert judged == 45_000 and round(cost, 2) == 94.50
    assert round(monthly_judge_cost(900_000, 1.0, 1500, 150, 1.0, 4.0)[1],
                 2) == 1890.00


# ---- every number the chapter prints in prose -------------------------
def test_try_it_yourself_answers():
    judge, expert = labels_from_matrix(78, 16, 2, 4)           # exercise 1
    assert observed_agreement(judge, expert) == 0.82
    assert round(chance_agreement(judge, expert), 2) == 0.76
    assert round(cohen_kappa(judge, expert), 2) == 0.24
    assert tpr_tnr(judge, expert)[1] == 0.2
    fair = JudgeConfig("fair", replace(B, first=0))             # exercise 2
    t = tally(fair, PAIRS)
    assert (round(t["x"], 2), round(t["y"], 2), round(t["tie"], 2)) == \
        (0.42, 0.44, 0.14)
    assert round(tally(fair, PAIRS, swap=True)["tie"], 2) == 0.46
    votes = [5, 4, 1]                                           # exercise 3
    assert round(aggregate(votes, "mean"), 2) == 3.33
    assert aggregate(votes, "median") == 4
    assert aggregate(votes, "majority") == "pass"
    assert round(aggregate(votes, "weighted", [0.2, 0.2, 0.8]), 2) == 2.17


def test_check_your_understanding_answers():
    expert = ["pass"] * 95 + ["fail"] * 5                       # question 1
    always = ["pass"] * 100
    assert observed_agreement(always, expert) == 0.95
    assert cohen_kappa(always, expert) == 0.0
    assert tpr_tnr(always, expert)[1] == 0.0
    judge, expert = labels_from_matrix(46, 14, 4, 36)           # question 3
    assert confusion(judge, expert) == (46, 14, 4, 36)
    assert observed_agreement(judge, expert) == 0.82
    assert round(chance_agreement(judge, expert), 2) == 0.5
    assert round(cohen_kappa(judge, expert), 2) == 0.64
    assert landis_koch(cohen_kappa(judge, expert)) == "substantial"


def test_the_numbers_printed_in_the_story():
    old = make_answers(200, 21)
    new = friday_tweak(old, 22)
    assert f"{sum(a.quality >= 4 for a in old) / 200:.0%}" == "74%"
    assert f"{sum(a.quality >= 4 for a in new) / 200:.0%}" == "55%"
    dev, test = split(make_answers(240, 11))
    assert round(calibrate(V2, test)["kappa"], 2) == 0.82
    v3 = replace(V2, version="v3", anchored=False)
    assert round(calibrate(v3, test)["kappa"], 2) == 0.52
    assert round(calibrate(V1, dev)["kappa"], 2) == 0.39
    assert len(dev) == len(test) == 120
