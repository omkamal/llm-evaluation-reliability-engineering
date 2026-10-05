"""A semantic cache: reuse an answer when a question means the same.

The embedding is a toy (a bag of content words) so that the demo runs
offline. A real embedding model is better, and fails the same way on
two questions that differ in one word and need different answers.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass

STOP = {"a", "an", "the", "is", "are", "do", "does", "i", "my", "me",
        "can", "to", "of", "it", "what", "how", "when", "after", "for"}
NEGATIONS = {"not", "no", "never", "cannot", "without"}
NEVER_STORED = {"lookup_order"}    # an answer that read a customer's data


def embed(text):
    """Counts of content words, with a plural stripped."""
    words = re.findall(r"[a-z0-9$]+", text.lower())
    return Counter(w[:-1] if len(w) > 3 and w.endswith("s") else w
                   for w in words if w not in STOP)


def cosine(a, b):
    dot = sum(a[w] * b[w] for w in a)
    return dot / (math.sqrt(sum(v * v for v in a.values()))
                  * math.sqrt(sum(v * v for v in b.values())))


def slots(text):
    """Numbers, amounts and negations: if these differ, never reuse."""
    words = re.findall(r"[a-z0-9$]+", text.lower())
    return frozenset(w for w in words
                     if w in NEGATIONS or re.fullmatch(r"\$?\d+", w))


@dataclass
class Entry:
    scope: str        # the tenant whose terms this answer follows
    question: str
    answer: str
    sources: dict     # doc id -> fingerprint when the answer was made


class SemanticCache:
    def __init__(self, live_prints, threshold=0.85, slot_guard=True):
        self.live = live_prints          # doc id -> fingerprint today
        self.threshold, self.slot_guard = threshold, slot_guard
        self.entries, self.dropped = [], 0

    def store(self, scope, question, answer, sources, tools=()):
        """Keep an answer, unless it was built from a customer's data."""
        if set(tools) & NEVER_STORED:
            return False
        self.entries.append(Entry(scope, question, answer, sources))
        return True

    def changed(self, entry):
        """Has any document behind this answer changed since?"""
        return any(self.live(doc) != fingerprint
                   for doc, fingerprint in entry.sources.items())

    def lookup(self, scope, question):
        """The cached entry for this tenant, or None."""
        asked, best, best_score = embed(question), None, 0.0
        for e in self.entries:
            if e.scope != scope:         # a hit never crosses tenants
                continue
            if self.slot_guard and slots(e.question) != slots(question):
                continue
            score = cosine(asked, embed(e.question))
            if score >= self.threshold and score > best_score:
                best, best_score = e, score
        if best and self.changed(best):
            self.entries.remove(best)    # a source changed: expire it
            self.dropped += 1
            return None
        return best
