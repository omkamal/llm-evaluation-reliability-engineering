"""Chapter 8 as tests. `pytest -q ch08_rag`"""
from dataclasses import replace
from datetime import date

import pytest

from ch05_judge.agreement import cohen_kappa
from ch08_rag.bm25 import BM25Index, Hit, stem, tokens
from ch08_rag.calibration import LABELED, agreement, judge_verdicts
from ch08_rag.chunker import chunk_all, chunk_doc
from ch08_rag.corpus import ALL_VERSIONS, DOCS, snapshot
from ch08_rag.generator import ABSTAIN, MODES, Answer, answer
from ch08_rag.grounding import (citation_problem, correct, groundedness,
                                supported)
from ch08_rag.lifecycle import (IndexRegistry, build_index, find_conflicts,
                                fingerprint, freshness_alarm, release_gate,
                                stale_docs)
from ch08_rag.metrics import (best_precision, context_precision, evaluate,
                              fact_recall, hit, leaks, recall,
                              reciprocal_rank)
from ch08_rag.queries import QUERIES
from ch08_rag.sweep import fact_recall_curve, sweep
from ch08_rag.tool import lookup_policy
from ch08_rag.triage import diagnose

TODAY = date(2026, 10, 4)
CURRENT = {d.id: d for d in DOCS}
BY_ID = {q.id: q for q in QUERIES}
DOC_TEXT = {d.id: d.text for d in DOCS}


@pytest.fixture(scope="module")
def v1():
    return build_index("v1", snapshot(date(2026, 9, 1)), date(2026, 9, 1))


@pytest.fixture(scope="module")
def v2():
    return build_index("v2", snapshot(TODAY), TODAY)


def run(index, qid, mode="grounded", k=3):
    q = BY_ID[qid]
    hits = index.bm25.search(q.text, k=k)
    return q, hits, answer(q.text, hits, mode, q.must)


# ---- the corpus and the labeled queries ---------------------------------
def test_the_policy_sheet_facts_are_in_the_documents():
    facts = {"returns": "14 days", "refund-timing": "5 business days",
             "damaged": "7 days", "reschedule": "2 times per parcel",
             "delivery-windows": "8:00 and 20:00, Monday to Saturday",
             "lost-parcel": "5 business days", "refund-approval": "$50",
             "address-change": "out for delivery",
             "free-shipping": "$60", "support-hours": "8:00 to 20:00"}
    for doc_id, fact in facts.items():
        assert fact in DOC_TEXT[doc_id]


def test_documents_are_dated_and_versioned():
    assert len(DOCS) == 11 and len({d.id for d in DOCS}) == 11
    assert all(d.version >= 1 and d.last_updated < TODAY for d in DOCS)


def test_old_versions_are_kept_so_we_can_ask_what_was_live_on_a_day():
    old = {d.id: d for d in snapshot(date(2026, 9, 1))}["free-shipping"]
    new = {d.id: d for d in snapshot(TODAY)}["free-shipping"]
    assert (old.version, "$40" in old.text) == (1, True)
    assert (new.version, "$60" in new.text) == (2, True)
    assert snapshot(TODAY) == DOCS


def test_fifty_labeled_queries_every_label_checked_against_the_documents():
    assert len(QUERIES) == 50 and len({q.id for q in QUERIES}) == 50
    assert sum(q.answerable for q in QUERIES) == 44
    for q in QUERIES:
        assert all(g in DOC_TEXT for g in q.gold)
        for doc_id in q.gold:        # every gold document is needed ...
            assert any(f.lower() in DOC_TEXT[doc_id].lower() for f in q.must)
        for fact in q.must:          # ... and every fact is written down
            assert any(fact.lower() in DOC_TEXT[g].lower() for g in q.gold)


def test_no_fact_is_credited_from_a_wrong_page():
    """Fact recall counts a fact wherever it appears; at the chapter's
    settings every credited fact comes from a right page."""
    for size in (12, 24, 48, 96):
        idx = BM25Index(chunk_all(DOCS, size, size // 4))
        for q in (q for q in QUERIES if q.answerable):
            hits = idx.search(q.text, k=10)
            for k in range(1, 11):
                top = hits[:k]
                anywhere = fact_recall([h.chunk.text for h in top], q.must)
                right = fact_recall([h.chunk.text for h in top
                                     if h.chunk.doc_id in q.gold], q.must)
                assert anywhere == right, (size, q.id, k)


# ---- chunking -----------------------------------------------------------
def test_chunks_overlap_and_cover_every_word():
    doc = DOCS[0]
    chunks = chunk_doc(doc, size=20, overlap=5)
    words = doc.text.split()
    assert chunks[0].text.split() == words[:20]
    assert chunks[1].text.split()[:5] == words[15:20]      # the overlap
    assert chunks[-1].text.split()[-1] == words[-1]
    assert [c.id for c in chunks[:2]] == ["returns#0", "returns#1"]


def test_a_short_document_is_one_chunk_and_bad_overlap_is_refused():
    assert len(chunk_doc(DOCS[8], size=48, overlap=12)) == 1
    with pytest.raises(ValueError):
        chunk_doc(DOCS[0], size=10, overlap=10)


def test_the_chunk_counts_in_the_chapter():
    counts = {s: len(chunk_all(DOCS, s, s // 4)) for s in (12, 24, 48, 96)}
    assert counts == {12: 66, 24: 35, 48: 19, 96: 11}
    assert len(chunk_all(DOCS, 48, 12)) == 19


# ---- the keyword retriever ----------------------------------------------
def test_the_crude_stemmer_joins_the_forms_it_should():
    assert stem("returns") == stem("returned") == stem("return")
    assert stem("shipping") == stem("ship")
    assert stem("damaged") == stem("damage")
    assert stem("deliveries") == stem("delivery")
    assert tokens("What are the delivery windows?") == ["deliv", "window"] \
        or tokens("What are the delivery windows?") == ["delivery", "window"]


def test_rare_words_count_for_more_than_common_ones(v2):
    idx = v2.bm25
    assert idx.idf[stem("sunday")] > idx.idf[stem("order")]


def test_an_empty_index_is_refused():
    with pytest.raises(ValueError):
        BM25Index([])


def test_nothing_matching_means_nothing_returned(v2):
    assert v2.bm25.search("Where is your head office?") == []
    assert v2.bm25.search("zzz qqq") == []


def test_repeating_a_word_helps_less_and_less():
    from ch08_rag.chunker import Chunk
    chunks = [Chunk("a#0", "a", 1, "refund " * 1 + "x y z w"),
              Chunk("b#0", "b", 1, "refund " * 2 + "x y z"),
              Chunk("c#0", "c", 1, "refund " * 6 + "x"),
              Chunk("d#0", "d", 1, "other words here")]
    idx = BM25Index(chunks)
    scores = [idx.score({"refund"}, i) for i in range(3)]
    assert scores[0] < scores[1] < scores[2]
    assert scores[2] - scores[1] < 3 * (scores[1] - scores[0])


def test_search_is_deterministic_and_min_score_filters(v2):
    a = v2.bm25.search("How long do I have to return an item?", k=5)
    b = v2.bm25.search("How long do I have to return an item?", k=5)
    assert [h.chunk.id for h in a] == [h.chunk.id for h in b]
    assert a[0].score >= a[-1].score
    loose = v2.bm25.search("Can I pay with cryptocurrency?", k=3)
    assert [h.chunk.id for h in loose] == ["free-shipping#0"]    # noise
    assert v2.bm25.search("Can I pay with cryptocurrency?", 3, 3.5) == []


# ---- retrieval metrics --------------------------------------------------
def test_the_metrics_on_a_worked_example():
    ids, gold = ["refund-timing", "help-centre", "returns"], ("returns",)
    assert hit(ids, gold, 2) == 0 and hit(ids, gold, 3) == 1
    assert reciprocal_rank(ids, gold) == pytest.approx(1 / 3)
    assert reciprocal_rank(["a", "b"], gold) == 0.0
    assert context_precision(ids, gold, 3) == pytest.approx(1 / 3)
    two = ("returns", "refund-timing")
    assert recall(ids, two, 3) == 1.0 and recall(ids, two, 1) == 0.5
    assert context_precision([], gold, 3) is None     # nothing to judge
    assert recall(ids, (), 3) is None and fact_recall(["x"], ()) is None
    assert reciprocal_rank(ids, gold, k=2) == 0.0       # MRR@k, not MRR
    assert best_precision(3, 1) == pytest.approx(1 / 3)
    assert best_precision(1, 1) == 1.0 and best_precision(0, 2) is None


def test_fact_recall_counts_facts_not_documents():
    assert fact_recall(["within 14 days of delivery"], ("14 days",)) == 1
    assert fact_recall(["we will email you a label"], ("14 days",)) == 0
    assert fact_recall(["14 days"], ("14 days", "5 business days")) == 0.5


def test_the_retrieval_numbers_in_the_chapter(v2):
    r = evaluate(v2.bm25, QUERIES, k=3)
    assert r["n"] == 44
    assert round(r["hit"], 2) == 0.91 and round(r["recall"], 2) == 0.88
    assert round(r["rr"], 2) == 0.78 and round(r["precision"], 2) == 0.45
    assert round(r["facts"], 2) == 0.77
    assert round(r["best"], 2) == 0.63 and r["empty"] == 0
    lo, hi = r["hit_ci"]                        # Wilson, as in Chapter 4
    assert (round(lo, 2), round(hi, 2)) == (0.79, 0.96)
    missed = [q.id for q in QUERIES if q.answerable and not any(
        h.chunk.doc_id in q.gold for h in v2.bm25.search(q.text, k=3))]
    assert missed == ["Q14", "Q28", "Q29", "Q32"]


def test_document_recall_can_hide_a_chunking_miss(v2):
    q, hits, _ = run(v2, "Q02")
    assert hit([h.chunk.doc_id for h in hits], q.gold, 3) == 1   # found it
    assert fact_recall([h.chunk.text for h in hits], q.must) == 0  # but not 14 days


# ---- generation checks --------------------------------------------------
def test_grounded_mode_quotes_the_retrieved_fact_and_cites_it(v2):
    q, hits, a = run(v2, "Q01")
    assert "14 days" in a.text and a.cites == ("returns",)
    assert correct(a, q) and citation_problem(a, hits) is None


def test_an_empty_retrieval_is_a_legal_answer():
    a = answer("Where is your head office?", [], "grounded")
    assert a.abstained and a.text == ABSTAIN and a.cites == ()


def test_groundedness_catches_invented_numbers_and_extra_claims():
    ctx = DOC_TEXT["returns"]
    assert supported("Returns are accepted within 14 days.", ctx)
    assert not supported("Returns are accepted within 30 days.", ctx)
    two = "Returns are accepted within 14 days. Most refunds are instant."
    assert groundedness(two, ctx) == 0.5


def test_each_failure_mode_is_caught_by_its_check(v2):
    q, hits, _ = run(v2, "Q01")
    ctx = " ".join(h.chunk.text for h in hits)
    memory = answer(q.text, hits, "memory", q.must)
    assert "30 days" in memory.text
    assert groundedness(memory.text, ctx) == 0 and not correct(memory, q)
    assert citation_problem(memory, hits) == "cites nothing"
    over = answer(q.text, hits, "overreach", q.must)
    assert groundedness(over.text, ctx) == 0.5
    assert citation_problem(over, hits) == "a claim no cited page supports"
    fake = answer(q.text, hits, "fake_citation", q.must)
    assert "not retrieved" in citation_problem(fake, hits)
    assert groundedness(fake.text, ctx) == 1.0     # grounded, badly cited


def test_a_correct_answer_from_two_pages_cites_both_validly(v2):
    q, hits, a = run(v2, "Q44")
    assert set(a.cites) == {"free-shipping", "address-change"}
    assert correct(a, q) and citation_problem(a, hits) is None


def test_a_citation_that_backs_no_claim_is_caught(v2):
    q, hits, a = run(v2, "Q01")
    padded = Answer(a.text, a.cites + ("refund-timing",))
    assert "refund-timing" in {h.chunk.doc_id for h in hits}
    assert citation_problem(padded, hits) == "refund-timing supports no claim"


def test_fake_citation_still_works_when_every_page_was_retrieved():
    index = build_index("all", DOCS, TODAY, size=96, overlap=24)
    hits = [Hit(c, 1.0) for c in index.bm25.chunks]   # k = corpus size
    assert {h.chunk.doc_id for h in hits} == {d.id for d in DOCS}
    fake = answer("refund", hits, "fake_citation", ("refund",))
    assert citation_problem(fake, hits).endswith("was not retrieved")


# ---- the triage ---------------------------------------------------------
def test_triage_assigns_each_wrong_answer_to_one_owner(v1, v2):
    assert diagnose(*run(v2, "Q01"), CURRENT) == "ok"
    assert diagnose(*run(v2, "Q14"), CURRENT) == "retrieval fault"   # a miss
    assert diagnose(*run(v2, "Q02"), CURRENT) == "retrieval fault"   # passage
    assert diagnose(*run(v2, "Q01", "memory"), CURRENT) == "generation fault"
    # memory that happens to agree with the document is invisible to a
    # groundedness check: the answer is supported, so it passes
    assert diagnose(*run(v2, "Q05", "memory"), CURRENT) == "ok"
    assert diagnose(*run(v1, "Q25"), CURRENT) == "source fault"      # stale
    assert diagnose(*run(v2, "Q25"), CURRENT) == "ok"


def test_a_reader_distracted_by_clutter_is_a_generation_fault(v2):
    q, hits, _ = run(v2, "Q01")
    ctx = [h.chunk.text for h in hits]
    assert fact_recall(ctx, q.must) == 1        # the fact was in the prompt
    wrong = Answer("If you have not seen the refund after that, ask Relay "
                   "to check the status of your return.", ("refund-timing",))
    assert groundedness(wrong.text, " ".join(ctx)) == 1.0   # faithful ...
    assert diagnose(q, hits, wrong, CURRENT) == "generation fault"  # ...


def test_a_right_answer_for_the_wrong_reason_is_flagged(v2):
    assert diagnose(*run(v2, "Q01", "overreach"), CURRENT) \
        == "right but ungrounded"


def test_unanswerable_queries_want_an_abstention(v2):
    assert diagnose(*run(v2, "Q49"), CURRENT) == "ok"
    assert diagnose(*run(v2, "Q46"), CURRENT) == "generation fault"


def test_the_triage_tally_in_the_chapter(v2):
    from collections import Counter
    tally = Counter()
    for q in QUERIES:
        hits = v2.bm25.search(q.text, k=3)
        a = answer(q.text, hits, "grounded", q.must)
        tally[(q.answerable, diagnose(q, hits, a, CURRENT))] += 1
    assert tally == {(True, "ok"): 32, (True, "retrieval fault"): 12,
                     (False, "ok"): 3, (False, "generation fault"): 3}


# ---- chunk size ---------------------------------------------------------
def test_the_chunk_size_sweep_in_the_chapter():
    rows = {size: s for size, _, s in sweep(DOCS, QUERIES, [12, 24, 48, 96])}
    assert [round(rows[s]["facts"], 2) for s in rows] == [0.34, 0.70, 0.77, 0.92]
    assert [round(rows[s]["recall"], 2) for s in rows] == [0.83, 0.89, 0.88, 0.92]
    assert [round(rows[s]["words"]) for s in rows] == [34, 64, 116, 163]
    assert [round(rows[s]["precision"], 2) for s in rows] == [0.51, 0.50, 0.45, 0.36]
    # precision falls mostly because its ceiling falls: k = 3 whole pages
    assert [round(rows[s]["best"], 2) for s in rows] == [0.97, 0.91, 0.63, 0.39]


def test_at_the_same_number_of_words_the_gap_mostly_closes():
    small = evaluate(BM25Index(chunk_all(DOCS, 24, 6)), QUERIES, k=8)
    large = evaluate(BM25Index(chunk_all(DOCS, 96, 24)), QUERIES, k=3)
    assert (round(small["words"]), round(large["words"])) == (158, 163)
    assert (round(small["facts"], 2), round(large["facts"], 2)) == (0.86, 0.92)


def test_the_curves_behind_the_figure():
    small = fact_recall_curve(DOCS, QUERIES, 24)
    large = fact_recall_curve(DOCS, QUERIES, 96)
    assert small == sorted(small) and large == sorted(large)   # more k, no loss
    assert all(big >= little for big, little in zip(large, small))
    assert [round(v, 2) for v in (small[2], large[2])] == [0.70, 0.92]
    assert [round(v, 2) for v in (small[0], small[-1])] == [0.44, 0.90]
    assert [round(v, 2) for v in (large[0], large[-1])] == [0.64, 0.98]


# ---- freshness and the index lifecycle ----------------------------------
def test_the_freshness_alarm_names_the_stale_document_and_the_age(v1, v2):
    assert stale_docs(v1, DOCS) == ["free-shipping: indexed v1, source v2"]
    assert freshness_alarm(v1, DOCS, TODAY) == [
        "free-shipping: indexed v1, source v2",
        "index v1 is 33 days old (limit 30)"]
    assert freshness_alarm(v2, DOCS, TODAY) == []


def test_any_edit_changes_the_fingerprint_even_without_a_version_bump(v2):
    edited = [replace(d, text=d.text.replace("14 days", "30 days"))
              if d.id == "returns" else d for d in DOCS]
    assert fingerprint(edited[0]) != fingerprint(DOCS[0])
    assert stale_docs(v2, edited) == ["returns: text changed, still v3"]


def test_a_document_missing_from_the_index_is_reported():
    partial = build_index("p", [d for d in DOCS if d.id != "returns"], TODAY)
    assert "returns: missing from the index" in stale_docs(partial, DOCS)


def test_a_page_deleted_at_source_but_still_indexed_is_reported(v2):
    retired = [d for d in DOCS if d.id != "refund-approval"]
    assert stale_docs(v2, retired) == [
        "refund-approval: in the index, deleted at source"]
    assert freshness_alarm(v2, retired, TODAY) != []
    top = v2.bm25.search("Do large refunds need a person?", k=1)
    assert top[0].chunk.doc_id == "refund-approval"     # still served


def test_the_gate_blocks_a_rechunk_that_keeps_hits_but_loses_facts(v2):
    rechunk = build_index("v4", DOCS, TODAY, size=12, overlap=3)
    ok, why = release_gate(rechunk, v2, DOCS, QUERIES)
    assert not ok
    assert why == ["fact recall@3 fell from 0.77 to 0.34"]   # hit rate held


def test_the_release_gate_passes_a_good_reindex_and_blocks_a_bad_one(v1, v2):
    ok, why = release_gate(v2, v1, DOCS, QUERIES)
    assert ok and why == []
    forgot = build_index("v3", [d for d in DOCS if d.id != "returns"], TODAY)
    ok, why = release_gate(forgot, v2, DOCS, QUERIES)
    assert not ok
    assert why == ["returns: missing from the index",
                   "hit rate@3 fell from 0.91 to 0.84"]


def test_rollback_restores_the_previous_version(v1, v2):
    reg = IndexRegistry()
    reg.publish(v1)
    with pytest.raises(RuntimeError):
        reg.roll_back()
    reg.publish(v2)
    assert reg.live.label == "v2"
    assert reg.roll_back().label == "v1" and reg.live.label == "v1"


def test_two_versions_of_one_document_in_a_context_are_a_conflict():
    both = build_index("both", ALL_VERSIONS, TODAY)
    hits = both.bm25.search("Is shipping free?", k=3)
    assert find_conflicts(hits) == ["free-shipping"]
    clean = build_index("clean", DOCS, TODAY)
    assert find_conflicts(clean.bm25.search("Is shipping free?", k=3)) == []


# ---- access: who may read which page --------------------------------------
STAFF_ONLY = replace(DOCS[6], id="staff-refunds", title="Staff refunds",
                     text="Staff may approve a refund of up to $500 for a "
                     "large order without a second person.")


def test_the_access_filter_works_inside_the_search_not_after():
    index = build_index("acl", DOCS + [STAFF_ONLY], TODAY)
    customer = {d.id for d in DOCS}           # may not read staff pages
    query = "Who can approve a large refund of $500?"
    unfiltered = [h.chunk.doc_id for h in index.bm25.search(query, k=3)]
    assert leaks(unfiltered, customer) == ["staff-refunds"]      # a leak
    inside = index.bm25.search(query, k=3, allowed=customer)
    assert leaks([h.chunk.doc_id for h in inside], customer) == []
    assert len(inside) == 3                   # k readable chunks
    after = [d for d in unfiltered if d in customer]
    assert len(after) < 3                     # filtering late loses slots
    tool = lookup_policy(index, query, allowed=customer)
    assert all(not c["id"].startswith("staff") for c in tool["chunks"])


# ---- empty retrieval and the tool ----------------------------------------
def test_a_score_floor_trades_missed_abstentions_for_false_ones(v2):
    unans = [q for q in QUERIES if not q.answerable]
    ans = [q for q in QUERIES if q.answerable]
    table = []
    for floor in (0.0, 2.0, 3.5):
        empty = lambda q: not v2.bm25.search(q.text, 3, floor)
        table.append((sum(empty(q) for q in unans),
                      sum(empty(q) for q in ans)))
    assert table == [(3, 0), (4, 3), (6, 12)]


def test_lookup_policy_reports_status_and_the_index_version(v1, v2):
    ok = lookup_policy(v1, "Is shipping free?")
    assert ok["status"] == "ok" and ok["index_version"] == "v1"
    assert ok["chunks"][0]["id"] == "free-shipping#0"
    assert ok["chunks"][0]["doc_version"] == 1
    assert lookup_policy(v2, "Is shipping free?")["chunks"][0]["doc_version"] == 2
    empty = lookup_policy(v2, "Where is your head office?")
    assert empty["status"] == "empty" and empty["chunks"] == []


# ---- calibrating the groundedness check ---------------------------------
def test_the_groundedness_check_against_human_labels():
    a = agreement()
    assert (a["tp"], a["fp"], a["fn"], a["tn"]) == (13, 5, 2, 6)
    lo, hi = a["kappa_ci"]           # 26 labels: far too wide to gate on
    assert (round(lo, 2), round(hi, 2)) == (0.05, 0.76)
    assert round(a["tpr"], 2) == 0.87 and round(a["tnr"], 2) == 0.55
    assert round(a["kappa"], 2) == 0.43
    human = [h for *_, h in LABELED]
    assert round(cohen_kappa(judge_verdicts(), human), 2) == 0.43


def test_the_check_is_fooled_by_negation_and_swapped_subjects():
    ctx = DOC_TEXT["delivery-windows"]
    assert supported("We also deliver on Sundays.", ctx)     # false pass
    paraphrase = "You have a week to tell us, with a picture of the parcel."
    assert not supported(paraphrase, DOC_TEXT["damaged"])    # false fail


def test_every_mode_is_covered():
    assert set(MODES) == {"grounded", "memory", "overreach", "fake_citation"}


def test_the_explanations_given_for_the_misses_in_the_chapter(v2):
    texts = {c.id: c.text for c in v2.bm25.chunks}
    words = [len(d.text.split()) for d in DOCS]
    assert (min(words), max(words)) == (17, 74)       # short pages
    assert "14 days" not in texts["returns#0"]        # Q02: wrong passage
    assert "14 days" in texts["returns#1"]
    assert "support" not in DOC_TEXT["support-hours"].lower()      # Q29
    assert DOC_TEXT["help-centre"].lower().count("support hours") == 2
    for word in ("talk", "person"):                                # Q28
        assert word not in DOC_TEXT["support-hours"].lower()
    for word in ("smash", "money"):                                # Q32
        assert word not in DOC_TEXT["damaged"].lower()
    for word in ("time", "arrive"):                                # Q14
        assert word not in DOC_TEXT["delivery-windows"].lower()


# ---- the "Try it yourself" answers ---------------------------------------
def test_exercise_one_a_title_fixes_one_miss_and_not_the_other():
    edited = [replace(d, text="Support hours. " + d.text)
              if d.id == "support-hours" else d for d in DOCS]
    index = build_index("x", edited, TODAY)
    r = evaluate(index.bm25, QUERIES, k=3)
    assert round(r["hit"], 2) == 0.93 and round(r["hit"] * 44) == 41
    q29, q28 = BY_ID["Q29"], BY_ID["Q28"]
    top29 = [h.chunk.doc_id for h in index.bm25.search(q29.text, k=3)]
    top28 = [h.chunk.doc_id for h in index.bm25.search(q28.text, k=3)]
    assert "support-hours" in top29 and "support-hours" not in top28


def test_exercise_two_overlap_zero_is_one_query_better_which_is_noise():
    base = build_index("a", DOCS, TODAY)
    flat = build_index("b", DOCS, TODAY, size=48, overlap=0)
    a, b = (evaluate(i.bm25, QUERIES, k=3) for i in (base, flat))
    assert round(a["hit"] * 44) == 40 and round(b["hit"] * 44) == 41
    assert round(a["facts"], 2) == 0.77 and round(b["facts"], 2) == 0.80


def test_exercise_three_a_silent_edit_is_caught_by_the_fingerprint(v2):
    edited = [replace(d, text=d.text.replace("$60", "$65"))
              if d.id == "free-shipping" else d for d in DOCS]
    assert stale_docs(v2, edited) == ["free-shipping: text changed, still v2"]
    # a check on version numbers alone sees nothing
    assert all(v2.manifest[d.id][0] == d.version for d in edited)


def test_the_demo_prints_what_the_chapter_shows(capsys):
    from ch08_rag.demo import main
    main()
    out = capsys.readouterr().out
    for line in ("hit rate@3         0.91  (95% interval 0.79 to 0.96)",
                 "context precision  0.45  (best possible 0.63)",
                 "Q03 reciprocal rank 0.33",
                 "diagnosis: source fault",
                 "gate v3: BLOCK",
                 "gate v4, 12-word chunks: BLOCK",
                 "live: v2 | after roll back: v1",
                 "TPR 0.87, TNR 0.55, kappa 0.43 (95% interval 0.05 to "
                 "0.76)"):
        assert line in out.splitlines()
    assert max(len(line) for line in out.splitlines()) <= 74
