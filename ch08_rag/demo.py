"""Every Chapter 8 output.   python3 -m ch08_rag.demo"""
from collections import Counter
from datetime import date

from ch08_rag.calibration import agreement
from ch08_rag.corpus import ALL_VERSIONS, DOCS, snapshot
from ch08_rag.generator import MODES, answer
from ch08_rag.grounding import citation_problem, correct, groundedness
from ch08_rag.lifecycle import (IndexRegistry, build_index,
                                find_conflicts, freshness_alarm,
                                release_gate)
from ch08_rag.metrics import evaluate, reciprocal_rank
from ch08_rag.queries import QUERIES
from ch08_rag.sweep import sweep
from ch08_rag.tool import lookup_policy
from ch08_rag.triage import diagnose

TODAY = date(2026, 10, 4)
CURRENT = {d.id: d for d in DOCS}
BY_ID = {q.id: q for q in QUERIES}


def show_retrieval(index):
    print("== retrieval, k=3")
    n_ans = sum(q.answerable for q in QUERIES)
    print(f"{len(DOCS)} documents, {len(index.bm25.chunks)} chunks, "
          f"{len(QUERIES)} queries ({n_ans} answerable)")
    r = evaluate(index.bm25, QUERIES, k=3)
    lo, hi = r["hit_ci"]
    print(f"hit rate@3         {r['hit']:.2f}  (95% interval "
          f"{lo:.2f} to {hi:.2f})")
    print(f"recall@3           {r['recall']:.2f}")
    print(f"MRR                {r['rr']:.2f}")
    print(f"context precision  {r['precision']:.2f}")
    print(f"fact recall@3      {r['facts']:.2f}")
    q = BY_ID["Q03"]
    ids = [h.chunk.doc_id for h in index.bm25.search(q.text, k=3)]
    print(f"{q.id} {q.text} -> {', '.join(ids)}")
    print(f"{q.id} reciprocal rank {reciprocal_rank(ids, q.gold):.2f}")
    missed = [q.id for q in QUERIES if q.answerable and not any(
        h.chunk.doc_id in q.gold
        for h in index.bm25.search(q.text, k=3))]
    print("missed at k=3:", ", ".join(missed))


def show_generation(index):
    print("== generation checks, Q01")
    q = BY_ID["Q01"]
    hits = index.bm25.search(q.text, k=3)
    context = " ".join(h.chunk.text for h in hits)
    print("mode           grounded  answer  citation")
    for mode in MODES:
        a = answer(q.text, hits, mode, q.must)
        problem = citation_problem(a, hits) or ("none" if not a.cites
                                                else "ok")
        right = "right" if correct(a, q) else "wrong"
        print(f"{mode:13} {groundedness(a.text, context):9.2f}  "
              f"{right:6}  {problem}")


def show_triage(index):
    print("== triage, grounded mode")
    tally = {True: Counter(), False: Counter()}
    partial = 0
    for q in QUERIES:
        hits = index.bm25.search(q.text, k=3)
        a = answer(q.text, hits, "grounded", q.must)
        verdict = diagnose(q, hits, a, CURRENT)
        tally[q.answerable][verdict] += 1
        found = {h.chunk.doc_id for h in hits} & set(q.gold)
        partial += verdict == "retrieval fault" and bool(found)
    for answerable, label in ((True, "answerable (44)"),
                              (False, "unanswerable (6)")):
        parts = [f"{v} {k}" for k, v in tally[answerable].most_common()]
        print(f"{label}: {', '.join(parts)}")
    faults = tally[True]["retrieval fault"]
    print(f"{faults} retrieval faults: {faults - partial} found no right "
          f"document,")
    print(f"{partial} found one but missed a fact")


def show_stale(v1):
    print("== a stale index")
    q = BY_ID["Q25"]
    hits = v1.bm25.search(q.text, k=3)
    a = answer(q.text, hits, "grounded", q.must)
    print(f"{q.text} -> {a.text}")
    print("diagnosis:", diagnose(q, hits, a, CURRENT))
    for alert in freshness_alarm(v1, DOCS, TODAY):
        print("alarm:", alert)


def show_chunks():
    print("== chunk size, k=3")
    print("words chunks doc-recall fact-recall precision context-words")
    for size, n, s in sweep(DOCS, QUERIES, [12, 24, 48, 96]):
        print(f"{size:5} {n:6} {s['recall']:10.2f} {s['facts']:11.2f}"
              f" {s['precision']:9.2f} {s['words']:13.0f}")


def show_lifecycle(v1):
    print("== re-index as a release")
    v2 = build_index("v2", snapshot(TODAY), TODAY)
    print("v2 alarm:", freshness_alarm(v2, DOCS, TODAY) or "none")
    ok, _ = release_gate(v2, v1, DOCS, QUERIES)
    print("gate v2:", "pass" if ok else "BLOCK")
    forgot = build_index("v3", [d for d in DOCS if d.id != "returns"],
                         TODAY)
    ok, why = release_gate(forgot, v2, DOCS, QUERIES)
    print("gate v3:", "pass" if ok else "BLOCK")
    for reason in why:
        print("  ", reason)
    reg = IndexRegistry()
    reg.publish(v1)
    reg.publish(v2)
    print("live:", reg.live.label, "| after roll back:",
          reg.roll_back().label)
    both = build_index("both", ALL_VERSIONS, TODAY)
    hits = both.bm25.search("Is shipping free?", k=3)
    print("one context, two versions of:", find_conflicts(hits))


def show_empty(index):
    print("== empty retrieval")
    unans = [q for q in QUERIES if not q.answerable]
    answerable = [q for q in QUERIES if q.answerable]
    print("min_score  right 'I do not know'  wrongly empty")
    for floor in (0.0, 2.0, 3.5):
        empty = lambda q: not index.bm25.search(q.text, 3, floor)
        right = sum(empty(q) for q in unans)
        wrong = sum(empty(q) for q in answerable)
        print(f"{floor:9.1f}  {right:>9} of {len(unans)}"
              f"  {wrong:>14} of {len(answerable)}")


def show_calibration():
    print("== calibrating the groundedness check")
    a = agreement()
    print(f"judge pass/fail vs human: tp {a['tp']}, fp {a['fp']}, "
          f"fn {a['fn']}, tn {a['tn']}")
    print(f"TPR {a['tpr']:.2f}, TNR {a['tnr']:.2f}, "
          f"kappa {a['kappa']:.2f}")


def show_tool(v1):
    print("== lookup_policy")
    for query in ("Is shipping free?", "Where is your head office?"):
        r = lookup_policy(v1, query)
        first = r["chunks"][0]["id"] if r["chunks"] else "-"
        print(f"{r['status']:5} index {r['index_version']}  {first}")


def main():
    v1 = build_index("v1", snapshot(date(2026, 9, 1)), date(2026, 9, 1))
    index = build_index("v2", snapshot(TODAY), TODAY)
    show_retrieval(index)
    show_generation(index)
    show_triage(index)
    show_stale(v1)
    show_chunks()
    show_lifecycle(v1)
    show_empty(index)
    show_calibration()
    show_tool(v1)


if __name__ == "__main__":
    main()
