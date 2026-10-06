"""RAG drift and alerting, as tests."""
from datetime import date

from ch08_rag.corpus import DOCS
from ch08_rag.lifecycle import freshness_alarm
from ch08_rag.tool import lookup_policy
from ch13_drift.alerts import (ALERT_LOG, fortnight_false_alarms,
                               group_incidents, median_alert_days, review,
                               route)
from ch13_drift.rag_drift import CUSTOMS, drift_table, make_index


def test_fresh_index_stale_questions():
    index = make_index()
    assert freshness_alarm(index, DOCS, date(2026, 10, 4)) == []
    empty = [q for q in CUSTOMS
             if lookup_policy(index, q)["status"] == "empty"]
    assert len(empty) >= 4          # no page covers customs questions


def test_zero_result_rate_leaves_its_band_in_week_6_and_alerts_in_7():
    rows, (lo, hi), alert = drift_table(make_index())
    assert [r[3] for r in rows[:5]] == [False] * 5      # baseline is quiet
    assert [r[3] for r in rows[5:]] == [True] * 3
    assert alert == 7
    assert rows[-1][4] > 0.1 > rows[0][4]               # pages-read PSI
    assert 0.10 < lo < hi < 0.17


def test_route_by_business_risk():
    assert route(True, True) == "page"
    assert route(False, True) == "ticket"
    assert route(True, False) == "ticket"     # one money window: not lost
    assert route(False, False) == "dashboard"      # not persistent
    assert route(True, True, enough_data=False) == "dashboard"


def test_high_volume_needs_the_band_from_history():
    plain, wide = fortnight_false_alarms()
    assert (plain, wide) == (0.682, 0.017)   # standard error cries wolf
    plain, wide = fortnight_false_alarms(runs=300, swing=0.0)
    assert plain < 0.05 and wide < 0.05      # luck only: both are fine


def test_grouping_turns_a_burst_into_one_incident():
    burst = [(1, "EU email"), (2, "EU email"), (3, "EU email")]
    assert len(group_incidents(burst)) == 1
    assert len(group_incidents(burst + [(30, "EU email")])) == 2
    assert len(group_incidents([(1, "EU email"), (1, "EU chat")])) == 2


def test_alert_review_precision():
    rows = {r[0]: r for r in review(ALERT_LOG)}
    rule = "good rate down, 1 window"
    assert rows[rule][4] == 2 / 11 and rows[rule][5] == "tighten"
    assert rows["tool-mix PSI over 0.25"][5] == "keep"
    assert rows["answer-length PSI over 0.1"][5] == "dashboard"  # 0 acted
    assert sum(r[2] for r in rows.values()) == 29       # fired in all


def test_leading_signals_alert_first():
    days = median_alert_days(200)
    steps = days["steps per task"][0]
    good = days["good-answer rate"][0]
    fcr = days["first-contact resolution"][0]
    assert (steps, good, fcr) == (2, 4, 5) and steps < 9      # day 9: Priya
