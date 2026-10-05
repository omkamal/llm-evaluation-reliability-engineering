"""Retrieval metrics. Judge the retriever alone: no generator involved.

Every function takes `doc_ids`, the retrieved chunks' document ids in rank
order (a document may appear more than once: one entry per chunk), and
`gold`, the ids of the documents that hold the answer.
"""
from ch04_numbers.stats import proportion_ci


def hit(doc_ids, gold, k):
    """1 if any gold document is among the top k chunks, else 0."""
    return int(any(d in gold for d in doc_ids[:k]))


def recall(doc_ids, gold, k):
    """Share of the gold documents found in the top k chunks."""
    return len(set(doc_ids[:k]) & set(gold)) / len(gold)


def reciprocal_rank(doc_ids, gold):
    """1 / rank of the first gold document; 0 if none was retrieved."""
    for rank, d in enumerate(doc_ids, start=1):
        if d in gold:
            return 1 / rank
    return 0.0


def context_precision(doc_ids, gold, k):
    """Share of the top k chunks that come from a gold document."""
    top = doc_ids[:k]
    return sum(d in gold for d in top) / len(top) if top else 0.0


def fact_recall(chunk_texts, must):
    """Share of the required facts that appear in the retrieved text."""
    text = " ".join(chunk_texts).lower()
    return sum(fact.lower() in text for fact in must) / len(must)


def evaluate(index, queries, k=3, min_score=0.0):
    """Average each metric over the answerable queries."""
    rows = []
    for query in queries:
        if not query.answerable:
            continue
        hits = index.search(query.text, k=k, min_score=min_score)
        ids = [h.chunk.doc_id for h in hits]
        rows.append({
            "hit": hit(ids, query.gold, k),
            "recall": recall(ids, query.gold, k),
            "rr": reciprocal_rank(ids, query.gold),
            "precision": context_precision(ids, query.gold, k),
            "facts": fact_recall([h.chunk.text for h in hits],
                                 query.must),
            "words": sum(len(h.chunk.text.split()) for h in hits),
        })
    n = len(rows)
    out = {name: sum(r[name] for r in rows) / n for name in rows[0]}
    out["n"] = n
    out["hit_ci"] = proportion_ci(sum(r["hit"] for r in rows), n)[2]
    return out
