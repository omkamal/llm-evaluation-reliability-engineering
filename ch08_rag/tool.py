"""`lookup_policy`: retrieval as a tool the model calls."""


def lookup_policy(index, query, k=3, min_score=2.0):
    """What the model sees, and what the trace should record."""
    hits = index.bm25.search(query, k=k, min_score=min_score)
    return {
        "status": "ok" if hits else "empty",   # empty is a legal outcome
        "index_version": index.label,          # which index answered
        "chunks": [{"id": h.chunk.id, "doc_version": h.chunk.version,
                    "score": round(h.score, 2), "text": h.chunk.text}
                   for h in hits],
    }
