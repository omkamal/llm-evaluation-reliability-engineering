"""The two-question triage: which stage owns a bad answer?"""
from ch08_rag.grounding import correct, groundedness
from ch08_rag.metrics import fact_recall


def diagnose(query, hits, answer, current):
    """Name the fault, or 'ok'. `current` maps doc id to its live Doc."""
    if not query.answerable:
        return "ok" if answer.abstained else "generation fault"
    ids = {h.chunk.doc_id for h in hits}
    context = " ".join(h.chunk.text for h in hits)
    grounded = (not answer.abstained
                and groundedness(answer.text, context) == 1.0)
    if correct(answer, query):
        return "ok" if grounded else "right but ungrounded"
    if not set(query.gold) <= ids:                 # question 1
        return "retrieval fault"
    if answer.abstained or not grounded:           # question 2
        return "generation fault"
    # Right document, faithful answer, still wrong: blame the source?
    live = " ".join(current[d].text for d in query.gold)
    stale = any(h.chunk.version != current[h.chunk.doc_id].version
                for h in hits if h.chunk.doc_id in query.gold)
    if stale or fact_recall([live], query.must) < 1:
        return "source fault"
    return "retrieval fault"       # the right page, but the wrong passage
