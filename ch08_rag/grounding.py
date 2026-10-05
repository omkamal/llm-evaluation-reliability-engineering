"""Generation checks: is the answer supported by what was retrieved?

`supported` is a crude lexical stand-in for an LLM judge (Chapter 5): a
claim counts as supported when most of its content words, and all of its
numbers, appear in the context. It is deterministic, which is why it is
here; it is also wrong in ways a real judge is wrong, so we calibrate it.
"""
from ch08_rag.bm25 import tokens
from ch08_rag.generator import sentences


def supported(claim, context, min_overlap=0.6):
    words, context_words = tokens(claim), set(tokens(context))
    if not words:
        return True
    covered = sum(w in context_words for w in words) / len(words)
    numbers_ok = all(w in context_words for w in words if w.isdigit())
    return covered >= min_overlap and numbers_ok


def groundedness(answer_text, context):
    """Share of the answer's claims (sentences) the context supports."""
    claims = sentences(answer_text)
    return sum(supported(c, context) for c in claims) / len(claims)


def citation_problem(answer, hits):
    """None if every citation is valid, else a short reason."""
    retrieved = {h.chunk.doc_id for h in hits}
    for doc_id in answer.cites:
        if doc_id not in retrieved:
            return f"cites {doc_id}, which was not retrieved"
        cited = " ".join(h.chunk.text for h in hits
                         if h.chunk.doc_id == doc_id)
        if groundedness(answer.text, cited) < 1.0:
            return f"{doc_id} does not support the answer"
    return None


def correct(answer, query):
    """Reference check: states every required fact (or abstains)."""
    if not query.answerable:
        return answer.abstained
    return all(f.lower() in answer.text.lower() for f in query.must)
