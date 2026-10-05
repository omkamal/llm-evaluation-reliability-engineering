"""The index as a release: versions, a freshness alarm, gate, rollback."""
import hashlib
from dataclasses import dataclass
from datetime import date

from ch08_rag.bm25 import BM25Index
from ch08_rag.chunker import chunk_all
from ch08_rag.metrics import evaluate


def fingerprint(doc):
    """A short hash of the text: any edit gives a different value."""
    return hashlib.sha256(doc.text.encode()).hexdigest()[:10]


@dataclass
class IndexVersion:
    label: str            # "v1", "v2"
    built_on: date
    manifest: dict        # doc id -> (version, fingerprint) as indexed
    bm25: BM25Index
    size: int = 48
    overlap: int = 12


def build_index(label, docs, built_on, size=48, overlap=12):
    manifest = {d.id: (d.version, fingerprint(d)) for d in docs}
    bm25 = BM25Index(chunk_all(docs, size, overlap))
    return IndexVersion(label, built_on, manifest, bm25, size, overlap)


def stale_docs(index, source):
    """Documents whose live source no longer matches what was indexed."""
    problems = []
    for doc in source:
        indexed = index.manifest.get(doc.id)
        if indexed is None:
            problems.append(f"{doc.id}: missing from the index")
        elif indexed[0] != doc.version:
            problems.append(
                f"{doc.id}: indexed v{indexed[0]}, source v{doc.version}")
        elif indexed[1] != fingerprint(doc):
            problems.append(
                f"{doc.id}: text changed, still v{doc.version}")
    return problems


def freshness_alarm(index, source, today, max_age_days=30):
    """Messages that should page someone; an empty list means fresh."""
    alerts = stale_docs(index, source)
    age = (today - index.built_on).days
    if age > max_age_days:
        alerts.append(f"index {index.label} is {age} days old "
                      f"(limit {max_age_days})")
    return alerts


class IndexRegistry:
    """Serves one live version and remembers the ones before it."""

    def __init__(self):
        self.versions, self.history = {}, []

    @property
    def live(self):
        return self.versions[self.history[-1]]

    def publish(self, index):
        self.versions[index.label] = index
        self.history.append(index.label)

    def roll_back(self):
        if len(self.history) < 2:
            raise RuntimeError("no earlier version to roll back to")
        self.history.pop()
        return self.live


def release_gate(candidate, live, source, queries, k=3, margin=0.05):
    """Block a re-index that is stale or retrieves worse than live."""
    reasons = stale_docs(candidate, source)
    new = evaluate(candidate.bm25, queries, k)["hit"]
    old = evaluate(live.bm25, queries, k)["hit"]
    if new < old - margin:
        reasons.append(f"hit rate@{k} fell from {old:.2f} to {new:.2f}")
    return not reasons, reasons


def find_conflicts(hits):
    """Documents that appear in one context with more than one version."""
    seen = {}
    for h in hits:
        seen.setdefault(h.chunk.doc_id, set()).add(h.chunk.version)
    return sorted(d for d, versions in seen.items() if len(versions) > 1)
