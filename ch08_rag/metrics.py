"""Retrieval metrics. Judge the retriever alone: no generator involved.

Every function takes `doc_ids`, the retrieved chunks' document ids in rank
order (a document may appear more than once: one entry per chunk), and
`gold`, the ids of the documents that hold the answer. Recall, fact recall
and context precision return None when there is nothing to measure (no
gold documents or facts, nothing retrieved); averages skip those.
"""
from ch04_numbers.stats import wilson_ci


def hit(doc_ids, gold, k):
    """1 if any gold document is among the top k chunks, else 0."""
    return int(any(d in gold for d in doc_ids[:k]))


def recall(doc_ids, gold, k):
    """Share of the gold documents found in the top k chunks."""
    if not gold:
        return None
    return len(set(doc_ids[:k]) & set(gold)) / len(gold)


def reciprocal_rank(doc_ids, gold, k=None):
    """1 / rank of the first gold document in the top k; 0 if none."""
    for rank, d in enumerate(doc_ids[:k], start=1):
        if d in gold:
            return 1 / rank
    return 0.0


def context_precision(doc_ids, gold, k):
    """Share of the top k chunks that come from a gold document."""
    top = doc_ids[:k]
    return sum(d in gold for d in top) / len(top) if top else None


def best_precision(n_returned, gold_chunks):
    """The best context precision possible: with one right chunk in the
    index and three returned, it is 1/3, however good the ranking."""
    if not n_returned:
        return None
    return min(n_returned, gold_chunks) / n_returned


def fact_recall(chunk_texts, must):
    """Share of the required facts that appear in the retrieved text."""
    if not must:
        return None
    text = " ".join(chunk_texts).lower()
    return sum(fact.lower() in text for fact in must) / len(must)


def leaks(doc_ids, readable):
    """Retrieved documents the asking user may not read: must be none."""
    return sorted(set(doc_ids) - set(readable))


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def evaluate(index, queries, k=3, min_score=0.0):
    """Average each metric over the answerable queries."""
    rows = []
    for query in queries:
        if not query.answerable:
            continue
        hits = index.search(query.text, k=k, min_score=min_score)
        ids = [h.chunk.doc_id for h in hits]
        in_gold = sum(c.doc_id in query.gold for c in index.chunks)
        rows.append({
            "hit": hit(ids, query.gold, k),
            "recall": recall(ids, query.gold, k),
            "rr": reciprocal_rank(ids, query.gold, k),
            "precision": context_precision(ids, query.gold, k),
            "best": best_precision(len(ids), in_gold),
            "facts": fact_recall([h.chunk.text for h in hits],
                                 query.must),
            "words": sum(len(h.chunk.text.split()) for h in hits),
        })
    n = len(rows)
    out = {name: _mean(r[name] for r in rows) for name in rows[0]}
    out["n"] = n
    out["empty"] = sum(r["precision"] is None for r in rows)
    out["hit_ci"] = wilson_ci(sum(r["hit"] for r in rows), n)
    return out
