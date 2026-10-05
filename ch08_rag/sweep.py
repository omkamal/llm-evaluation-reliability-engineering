"""The chunk-size experiment: one number per setting, same queries."""
from ch08_rag.bm25 import BM25Index
from ch08_rag.chunker import chunk_all
from ch08_rag.metrics import evaluate, fact_recall


def fact_recall_curve(docs, queries, size, ks=range(1, 11)):
    """Fact recall@k for chunks of `size` words (a quarter overlaps)."""
    index = BM25Index(chunk_all(docs, size, size // 4))
    answerable = [q for q in queries if q.answerable]
    curve = []
    for k in ks:
        total = 0.0
        for q in answerable:
            hits = index.search(q.text, k=k)
            total += fact_recall([h.chunk.text for h in hits], q.must)
        curve.append(total / len(answerable))
    return curve


def sweep(docs, queries, sizes, k=3):
    """Compare chunk sizes at a fixed k."""
    rows = []
    for size in sizes:
        index = BM25Index(chunk_all(docs, size, size // 4))
        scores = evaluate(index, queries, k)
        rows.append((size, len(index.chunks), scores))
    return rows
