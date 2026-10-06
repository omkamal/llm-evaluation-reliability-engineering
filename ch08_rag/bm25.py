"""A keyword retriever written from scratch: BM25 scoring over chunks."""
import math
import re
from collections import Counter
from dataclasses import dataclass

STOP = set("""a an the is are was be to of in on for and or my i me do
does can you your it this that what when how with at as by from after if
about there we us our so get have has""".split())


def stem(word):
    """A crude stemmer: returns -> return, damaged and damage -> damag."""
    word = _strip_suffix(word)
    return word[:-1] if word.endswith("e") and len(word) > 4 else word


def _strip_suffix(word):
    if word.endswith("ss"):
        return word
    if word.endswith("ies") and len(word) > 5:
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            base = word[:-len(suffix)]
            if suffix in ("ing", "ed") and base[-1] == base[-2]:
                base = base[:-1]          # shipping -> shipp -> ship
            return base
    return word


def tokens(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(w) for w in words if w not in STOP]


@dataclass(frozen=True)
class Hit:
    chunk: object
    score: float


class BM25Index:
    def __init__(self, chunks, k1=1.2, b=0.75):
        self.chunks, self.k1, self.b = list(chunks), k1, b
        if not self.chunks:
            raise ValueError("an index needs at least one chunk")
        self.tf = [Counter(tokens(c.text)) for c in self.chunks]
        self.length = [sum(tf.values()) for tf in self.tf]
        self.avg = sum(self.length) / len(self.length)
        docs_with = Counter(w for tf in self.tf for w in tf)
        n = len(self.chunks)
        # rare words count for more: idf is high when few chunks have it
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5))
                    for w, d in docs_with.items()}

    def score(self, query_terms, i):
        tf, b = self.tf[i], self.b
        norm = 1 - b + b * self.length[i] / self.avg    # long chunks: > 1
        total = 0.0
        for w in query_terms:
            if w in tf:   # repeats saturate: the k1 term caps their value
                total += self.idf[w] * tf[w] * (self.k1 + 1) / (
                    tf[w] + self.k1 * norm)
        return total

    def search(self, query, k=5, min_score=0.0, allowed=None):
        """The k best chunks scoring above `min_score` (maybe none).

        `allowed` is the set of document ids the asking user may read
        (None: all). It filters before ranking, so the k slots go to
        readable chunks; filtering the k results afterwards would leave
        fewer than k, or none.
        """
        terms = set(tokens(query))
        scored = [(self.score(terms, i), i)
                  for i, c in enumerate(self.chunks)
                  if allowed is None or c.doc_id in allowed]
        scored = [(s, i) for s, i in scored if s > min_score]
        scored.sort(key=lambda si: (-si[0], si[1]))   # ties: doc order
        return [Hit(self.chunks[i], s) for s, i in scored[:k]]
