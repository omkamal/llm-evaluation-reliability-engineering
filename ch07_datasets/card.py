"""A dataset card with a content hash: which cases, exactly, made a score."""
import hashlib
import json
from collections import Counter
from dataclasses import dataclass


def content_hash(cases):
    """Same cases give the same hash, whatever order they are stored in."""
    ordered = sorted(cases, key=lambda c: c["id"])
    canon = json.dumps(ordered, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class DatasetCard:
    name: str
    version: int
    created: str            # passed in, so the code stays deterministic
    owner: str
    guideline: int          # which labeling guideline made the labels
    n_cases: int
    sources: tuple          # (source, count) pairs
    known_gaps: tuple
    content_hash: str

    def label(self):
        """What a score should carry next to the number."""
        return f"{self.name} v{self.version} ({self.content_hash})"


def make_card(name, version, cases, *, created, owner, guideline,
              known_gaps):
    counts = Counter(c["source"] for c in cases)
    sources = tuple(sorted(counts.items(), key=lambda p: (-p[1], p[0])))
    return DatasetCard(name, version, created, owner, guideline,
                       len(cases), sources, tuple(known_gaps),
                       content_hash(cases))


def matches(card, cases):
    """False means the cases changed without a new version."""
    return card.content_hash == content_hash(cases)


def render(card):
    mix = ", ".join(f"{s} {n}" for s, n in card.sources)
    lines = [f"{card.name}, version {card.version} (hash "
             f"{card.content_hash})",
             f"  cases:      {card.n_cases} ({mix})",
             f"  owner:      {card.owner}",
             f"  created:    {card.created}",
             f"  guideline:  v{card.guideline}"]
    for i, gap in enumerate(card.known_gaps):
        head = "gaps:" if i == 0 else ""
        lines.append(f"  {head:<12}{gap}")
    return "\n".join(lines)
