"""Chapter 7 behaviours as tests. `pytest -q ch07_datasets`"""
import pytest

from ch05_judge.agreement import confusion
from ch07_datasets import labeling
from ch07_datasets.card import content_hash, make_card, matches, render
from ch07_datasets.contamination import find_leaks, overlap
from ch07_datasets.demo import REFERENCES
from ch07_datasets.golden import golden_card, golden_v3
from ch07_datasets.implicit import hints, similar, thumbs_share
from ch07_datasets.labeling import (make_items, majority_right, summary)
from ch07_datasets.redact import luhn_ok, redact
from ch07_datasets.relay_cases import (MONDAY_TEXTS, edge_cases,
                                       from_trace, monday_cases,
                                       traffic_log)
from ch07_datasets.sampling import (coverage, in_online_sample,
                                    random_sample, score_record,
                                    stratified_sample)
from ch07_datasets.sandbox import (LiveTenantError, Tenant, bind_orders,
                                   require_test_tenant, seed_orders)
from ch07_datasets.scripted import CONVERSATIONS, conv

LOG = traffic_log()


# --- where cases come from ------------------------------------------------
def test_stratified_covers_every_group_and_random_does_not():
    assert coverage(LOG) == 54
    assert coverage(stratified_sample(LOG, 60)) == 54
    assert coverage(random_sample(LOG, 60)) == 29


def test_stratified_sample_has_no_duplicates_and_respects_n():
    picked = stratified_sample(LOG, 36)
    assert len(picked) == 36
    assert len({r["id"] for r in picked}) == 36
    assert coverage(picked) == 36        # one from each of 36 groups


def test_the_monday_cases_forbid_a_reschedule():
    cases = monday_cases()
    assert len(cases) == 12
    assert all("reschedule_delivery" in c["forbidden"] for c in cases)
    assert all(c["move"] == "answer" for c in cases)


def test_edge_cases_name_the_right_move():
    moves = {c["id"]: c["move"] for c in edge_cases()}
    assert moves["E-3"] == "clarify"           # "next Friday"
    assert moves["E-4"] == moves["E-5"] == "hand_off"


# --- versioning and the card ----------------------------------------------
def test_golden_set_has_four_sources_and_unique_ids():
    cases = golden_v3()
    assert len(cases) == 64 and len({c["id"] for c in cases}) == 64
    card = golden_card(cases)
    assert dict(card.sources) == {"trace": 48, "synthetic": 8,
                                  "edge": 5, "ticket": 3}


def test_hash_ignores_order_but_catches_any_edit():
    cases = golden_v3()
    card = golden_card(cases)
    assert matches(card, cases[::-1])
    edited = [dict(c) for c in cases]
    edited[0]["move"] = "clarify"
    assert not matches(card, edited)
    spaced = [dict(c) for c in cases]
    spaced[1]["text"] += " "                  # even a trailing space
    assert content_hash(spaced) != card.content_hash


def test_card_label_and_render_carry_version_and_hash():
    card = golden_card(golden_v3())
    assert card.label() == f"Relay golden set v3 ({card.content_hash})"
    text = render(card)
    assert "version 3" in text and card.content_hash in text
    assert "gaps:" in text and "guideline:  v2" in text
    assert all(len(line) <= 74 for line in text.splitlines())


def test_adding_a_case_changes_the_hash_not_the_version():
    cases = golden_v3()
    card = golden_card(cases)
    bigger = cases + [dict(cases[0], id="M-13")]
    again = make_card("Relay golden set", 3, bigger, created="2026-09-14",
                      owner="Marcus", guideline=2, known_gaps=())
    assert again.version == card.version == 3
    assert again.content_hash != card.content_hash
    assert again.n_cases == 65


# --- contamination --------------------------------------------------------
def test_copies_are_flagged_and_paraphrases_are_not():
    leaks = find_leaks(golden_v3(), REFERENCES)
    assert [(c, n) for c, n, _ in leaks] == [
        ("M-03", "judge_example_2"), ("M-05", "prompt_example_1")]
    assert overlap("Has my package shipped?",
                   REFERENCES["judge_example_3"]) == 0


def test_a_short_message_is_checked_whole_whatever_n_is():
    ref = "Customer asks: where is order ORD-004829? Expected: answer."
    assert overlap("Where is order ORD-004829?", ref, n=4) == 1.0
    assert overlap("Where is order ORD-004829?", ref, n=8) == 1.0
    assert overlap("Where is order ORD-004830?", ref, n=8) == 0.0


def test_the_tracker_paraphrase_slips_through():
    ref = "The tracker said today, so where is the parcel?"
    assert overlap("It said delivery today, where is it?", ref) == 0.0


def test_a_case_with_no_words_is_not_a_leak():
    assert overlap("?!", "any prompt at all") == 0.0
    assert find_leaks([{"id": "x", "text": "??"}], REFERENCES) == []


# --- labeling -------------------------------------------------------------
def test_guideline_v1_gives_low_kappa_and_v2_fixes_it():
    # v2 is checked on a fresh batch, not on the items that wrote it
    v1, v2 = summary(make_items(), 1), summary(make_items(seed=4), 2)
    assert round(v1["kappa"], 2) == 0.65 and round(v2["kappa"], 2) == 0.95
    lo1, hi1 = v1["kappa_ci"]
    lo2, hi2 = v2["kappa_ci"]
    assert (round(lo1, 2), round(hi1, 2)) == (0.53, 0.76)
    assert (round(lo2, 2), round(hi2, 2)) == (0.89, 0.99)
    assert hi1 < 0.8 < lo2          # each whole interval on its side


def test_kappa_interval_is_wide_on_50_items():
    # why the deliverable asks for 100 items: on 50, v1 cannot be told
    # apart from the 0.8 bar
    items = make_items(n=50)
    lo, hi = summary(items, 1)["kappa_ci"]
    assert lo < 0.8 < hi


def test_disagreements_cluster_on_the_kinds_the_guideline_skips():
    s = summary(make_items(), 1)
    silent = sum(n for k, n in s["disagreements"].items()
                 if k in labeling.SILENT)
    assert silent >= 0.9 * s["adjudicated"] - 3
    assert s["disagreements"] == {"credit demand": 7, "late parcel": 8,
                                  "next friday": 9, "plain": 2}


def test_agreeing_on_a_wrong_label_never_reaches_the_adjudicator():
    s = summary(make_items(), 1)
    assert s["agreed_wrong"] == 9 and s["final_right"] == 0.91
    assert summary(make_items(), 2)["final_right"] == 1.0


def test_more_labelers_do_not_fix_a_missing_rule():
    for k in (1, 3, 9):
        assert 0.45 <= majority_right(1, k) <= 0.55
    assert majority_right(2, 1) > 0.95 and majority_right(2, 9) == 1.0


def test_scattered_noise_is_absorbed_by_the_adjudicator(monkeypatch):
    monkeypatch.setattr(labeling, "SLIP", 0.10)
    s = summary(make_items(), 2)
    assert round(s["kappa"], 2) == 0.75
    assert s["disagreements"]["plain"] == 8 and s["adjudicated"] == 19
    assert s["final_right"] == 0.98 and s["agreed_wrong"] == 0


# --- online sampling and implicit feedback --------------------------------
def test_online_sample_is_about_five_percent_and_order_free():
    ids = [r["id"] for r in LOG if in_online_sample(r["id"])]
    assert len(ids) == 92 and 0.03 < len(ids) / len(LOG) < 0.07
    back = [r["id"] for r in reversed(LOG) if in_online_sample(r["id"])]
    assert sorted(back) == ids


def test_a_score_travels_with_its_trace_id():
    rec = score_record("C-00060", "pass")
    assert rec == {"trace_id": "C-00060", "judge": "judge_v2",
                   "verdict": "pass"}


def test_hints_on_scripted_conversations():
    found = {c["id"]: hints(c) for c in CONVERSATIONS}
    assert found["s1"] == ["rephrased"]
    assert found["s9"] == ["rephrased", "asked_for_human"]
    assert found["s3"] == ["reopened_48h"]
    assert found["s5"] == []            # reopened after 70 hours
    assert found["s8"] == []            # the silent failure: no hint


def test_hints_are_not_verdicts():
    flagged = ["miss" if hints(c) else "ok" for c in CONVERSATIONS]
    expert = [c["expert"] for c in CONVERSATIONS]
    assert confusion(flagged, expert, positive="miss") == (4, 2, 1, 2)
    assert hints(CONVERSATIONS[3]) == ["asked_for_human"]   # s4: fine
    assert hints(CONVERSATIONS[6]) == ["rephrased"]         # s7: fine


def test_wordless_turns_do_not_crash_the_hints():
    turns = [("customer", "??"), ("relay", "Sorry?"), ("customer", "??")]
    assert hints(conv("x", "ok", turns)) == []
    assert similar("??", "!!") == 0.0


def test_reopening_exactly_at_48_hours_counts_and_49_does_not():
    turns = [("customer", "hi")]
    assert hints(conv("x", "ok", turns, reopened=48)) == ["reopened_48h"]
    assert hints(conv("x", "ok", turns, reopened=49)) == []
    assert similar("where is my parcel", "where is my parcel") == 1.0


def test_same_quality_different_widget_different_thumbs():
    corner = thumbs_share(0.80, 0.02, 0.06)
    prompt = thumbs_share(0.80, 0.12, 0.08)
    assert round(corner[0], 2) == 0.57 and round(prompt[0], 2) == 0.86
    assert round(corner[1], 3) == 0.028 and round(prompt[1], 3) == 0.112


# --- redaction -------------------------------------------------------------
def test_redactor_removes_the_patterns_it_knows():
    text, found = redact("Mail anna.keller@example.com about ORD-004829, "
                         "call +49 170 1234567.")
    assert text == "Mail <EMAIL_1> about <ORDER_1>, call <PHONE_1>."
    assert found == {"EMAIL": 1, "ORDER": 1, "PHONE": 1}


def test_same_value_gets_the_same_placeholder():
    text, found = redact("ORD-004829 and ORD-004830, again ORD-004829")
    assert text == "<ORDER_1> and <ORDER_2>, again <ORDER_1>"
    assert found == {"ORDER": 3}


def test_card_numbers_need_a_valid_check_digit():
    assert luhn_ok("4111 1111 1111 1111")
    text, _ = redact("paid with 4111 1111 1111 1111 twice")
    assert text == "paid with <CARD_1> twice"
    text, found = redact("reference 1234 5678 9012 3456 here")
    assert "CARD" not in found


def test_dates_are_not_mistaken_for_phone_numbers():
    text, found = redact("delivered on 2026-12-07")
    assert text == "delivered on 2026-12-07" and found == {}


def test_the_redactor_misses_names_and_addresses_and_we_know_it():
    text = "Hannelore Vogt, Lindenstrasse 12, 50667 Koeln. Parcel is next door."
    assert redact(text) == (text, {})


# --- test environments -------------------------------------------------------
def test_evals_refuse_a_live_tenant():
    require_test_tenant(Tenant("eval-sandbox", "test"))
    with pytest.raises(LiveTenantError, match="crateway-prod"):
        require_test_tenant(Tenant("crateway-prod", "live"))


def test_a_test_tenant_with_a_real_looking_name_is_refused_too():
    with pytest.raises(LiveTenantError):
        require_test_tenant(Tenant("crateway-prod", "test"))
    with pytest.raises(LiveTenantError):
        require_test_tenant(Tenant("eval-sandbox", "live"))


def test_a_trace_case_is_bound_to_a_seeded_order():
    assert MONDAY_TEXTS[1] == "Where is order <ORDER_1>?"
    assert from_trace(MONDAY_TEXTS[1]) == "Where is order ORD-900001?"
    assert from_trace("Order ORD-004829 is late") == "Order ORD-900001 is late"
    with pytest.raises(ValueError):
        bind_orders("<ORDER_1> <ORDER_2> <ORDER_3> <ORDER_4>", seed_orders())


def test_every_order_in_the_golden_set_exists_in_the_test_tenant():
    import re
    seeded = {o["order_id"] for o in seed_orders()}
    named = {m for c in golden_v3()
             for m in re.findall(r"ORD-\d{6}|<ORDER_\d+>", c["text"])}
    assert named and named <= seeded


def test_seeded_orders_are_fake_deterministic_and_in_a_reserved_range():
    orders = seed_orders()
    assert orders == seed_orders()
    assert [o["order_id"] for o in orders] == [
        "ORD-900001", "ORD-900002", "ORD-900003"]
    assert all(o["customer"].startswith("Test Customer") for o in orders)
