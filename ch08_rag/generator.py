"""A deterministic stand-in for the generator, so everything runs offline.

`answer` plays the model. In `grounded` mode it is an oracle reader: if a
retrieved sentence states a required fact it quotes it, and cites its
document; if not, it quotes the best-matching sentence anyway, which is
how a confident model answers from the wrong book. The other modes play
the ways a real model goes wrong, so we can test the checks that catch
them. In your system this is the one function that calls the model.
"""
import re
from dataclasses import dataclass

from common.relay_fake import ask
from ch08_rag.bm25 import tokens
from ch08_rag.corpus import DOCS

ABSTAIN = "I could not find that in the policy documents."
MODES = ("grounded", "memory", "overreach", "fake_citation")


@dataclass(frozen=True)
class Answer:
    text: str
    cites: tuple = ()

    @property
    def abstained(self):
        return self.text == ABSTAIN


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def pick_sentences(question, hits, must):
    """(sentence, doc id) pairs: those stating a fact, else best match."""
    pairs = [(s, h.chunk.doc_id) for h in hits
             for s in sentences(h.chunk.text)]
    stating = [(s, d) for s, d in pairs
               if any(f.lower() in s.lower() for f in must)]
    if stating:
        return list(dict.fromkeys(stating))      # no duplicates, in order
    wanted = set(tokens(question))
    return [max(pairs, key=lambda p: len(wanted & set(tokens(p[0]))))]


def answer(question, hits, mode="grounded", must=()):
    if mode == "memory":      # ignores the context, answers from habit
        return Answer(ask(question, "v2"))
    if not hits:              # nothing retrieved: saying so is legal
        return Answer(ABSTAIN)
    picked = pick_sentences(question, hits, must)
    text = " ".join(s for s, _ in picked)
    cites = tuple(dict.fromkeys(d for _, d in picked))
    if mode == "overreach":   # adds a claim nobody retrieved
        text += " Most refunds are instant."
    if mode == "fake_citation":   # cites a page that was not retrieved
        seen = {h.chunk.doc_id for h in hits}
        cites = (next(d.id for d in DOCS if d.id not in seen),)
    return Answer(text, cites)
