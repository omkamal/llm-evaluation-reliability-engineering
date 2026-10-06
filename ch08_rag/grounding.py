"""Generation checks: is the answer supported by what was retrieved?

`supported` is a crude lexical stand-in for an LLM judge (Chapter 5): a
claim counts as supported when most of its content words, and all of its
numbers, appear in the context. It is deterministic, which is why it is
here; like any judge it makes mistakes (it is blind to negation and to
paraphrase), so we calibrate it.
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
    """None if the citations hold up, else a short reason.

    Every cited page must have been retrieved and back at least one
    claim, and every claim must be backed by some page it cites. An
    answer that cites nothing fails (a product that promises citations
    owes one); an abstention needs none.
    """
    if answer.abstained:
        return None
    if not answer.cites:
        return "cites nothing"
    retrieved = {h.chunk.doc_id for h in hits}
    for doc_id in answer.cites:
        if doc_id not in retrieved:
            return f"cites {doc_id}, which was not retrieved"
    cited = {d: " ".join(h.chunk.text for h in hits
                         if h.chunk.doc_id == d) for d in answer.cites}
    claims = sentences(answer.text)
    for claim in claims:
        if not any(supported(claim, text) for text in cited.values()):
            return "a claim no cited page supports"
    for doc_id, text in cited.items():
        if not any(supported(claim, text) for claim in claims):
            return f"{doc_id} supports no claim"
    return None


def correct(answer, query):
    """Reference check: states every required fact (or abstains)."""
    if not query.answerable:
        return answer.abstained
    return all(f.lower() in answer.text.lower() for f in query.must)
