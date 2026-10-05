"""Drift-probe sets and the drifting judge, as tests."""
import random
from statistics import mean

from ch05_judge.agreement import cohen_kappa
from ch13_drift.bands import first_alert, noise_band
from ch13_drift.probe import (ALIAS, CASES, EXPERT, flipped_topics,
                              judge_band, judged_rate, monthly_kappa,
                              rerun_judge, run_probe, snapshot_behind)


def test_forty_fixed_cases_ten_topics():
    assert len(CASES) == 40 and len({t for _, t in CASES}) == 10


def test_alias_moves_and_a_pin_does_not():
    assert snapshot_behind(ALIAS, 14, 15) == "a-large-v1"
    assert snapshot_behind(ALIAS, 15, 15) == "a-large-v2"
    assert snapshot_behind("a-large-v1", 99, 15) == "a-large-v1"


def test_the_new_snapshot_really_is_worse_on_policy_numbers():
    rng = random.Random(0)
    v1 = mean(run_probe("a-large-v1", rng)[0] for _ in range(200))
    v2 = mean(run_probe("a-large-v2", rng)[0] for _ in range(200))
    assert v1 > 0.93 and v2 < 0.85


def test_alias_probe_alerts_on_day_16_and_the_pin_never_does():
    rng = random.Random(11)
    lo, _ = noise_band([run_probe("a-large-v1", rng)[0]
                        for _ in range(10)])
    rng = random.Random(1)
    alias, pinned = [], []
    for day in range(1, 22):
        alias.append(run_probe(snapshot_behind(ALIAS, day, 15), rng)[0])
        pinned.append(run_probe(snapshot_behind("a-large-v1", day, 15),
                                rng)[0])
    assert first_alert([v < lo for v in alias], 2) + 1 == 16
    assert first_alert([v < lo for v in pinned], 2) is None


def test_flipped_topics_names_the_topics_that_got_worse():
    before = ["returns-1", "damaged-2"]
    after = ["returns-1", "returns-2", "returns-3", "lost-parcel-1"]
    assert flipped_topics(before, after) == {"returns": 2,
                                             "lost-parcel": 1}


def test_held_out_set_matches_chapter_5_split():
    assert EXPERT.count("pass") == 78 and EXPERT.count("fail") == 42


def test_judge_drift_shows_as_kappa_below_the_band():
    lo, hi = judge_band(10)
    kappas = monthly_kappa(5, 5)
    assert all(lo <= k <= hi for k in kappas[:4])
    assert kappas[4] < lo
    again = rerun_judge(0.93, 0.70, random.Random(99))
    assert cohen_kappa(again, EXPERT) < lo      # confirmed on a re-run


def test_a_drifting_judge_can_make_decay_look_like_improvement():
    before = judged_rate(0.75, 0.93, 0.92)
    after = judged_rate(0.75, 0.93, 0.70)
    assert round(before, 4) == 0.7175 and round(after, 4) == 0.7725
    assert after > before                         # same answers, higher
