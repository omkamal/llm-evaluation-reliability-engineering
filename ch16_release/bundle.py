"""A release bundle: everything that decides Relay's behaviour, together.

Chapter 8 gave an index a manifest and a fingerprint. A bundle does the
same for the whole release: one id, one manifest, one fingerprint, and
one move to go back to the last good combination.
"""
import hashlib
import json
from dataclasses import dataclass

PARTS = ("prompt", "model", "tools", "index", "policy", "config")


def digest(content):
    """Short hash of the content itself, so a silent edit shows up."""
    text = content if isinstance(content, str) else json.dumps(
        content, sort_keys=True, default=list)
    return hashlib.sha256(text.encode()).hexdigest()[:10]


@dataclass(frozen=True)
class Bundle:
    id: str
    parts: dict        # part name -> (label, digest of its content)
    eval_set: str      # what it was tested on
    judge: str         # and which judge scored it

    def manifest(self):
        return {"id": self.id, "eval_set": self.eval_set,
                "judge": self.judge, "parts": dict(self.parts)}

    def fingerprint(self):
        text = json.dumps(self.manifest(), sort_keys=True)
        return hashlib.sha256(text.encode()).hexdigest()[:12]


def make_bundle(bundle_id, contents, eval_set, judge):
    """`contents` maps each part to (label, the content itself)."""
    missing = [p for p in PARTS if p not in contents]
    if missing:
        raise ValueError(f"a bundle needs every part; missing {missing}")
    parts = {p: (label, digest(body))
             for p, (label, body) in contents.items()}
    return Bundle(bundle_id, parts, eval_set, judge)


def changed_parts(old, new):
    """Which parts differ between two bundles, as 'part: old -> new'."""
    return [f"{p}: {old.parts[p][0]} -> {new.parts[p][0]}"
            for p in PARTS if old.parts[p] != new.parts[p]]


def drift(bundle, deployed):
    """Parts whose deployed content is not what the manifest recorded."""
    return [p for p in PARTS
            if digest(deployed[p]) != bundle.parts[p][1]]


class Registry:
    """One live bundle, and the ones before it."""

    def __init__(self):
        self.history = []

    @property
    def live(self):
        return self.history[-1]

    def promote(self, bundle):
        self.history.append(bundle)

    def roll_back(self):
        if len(self.history) < 2:
            raise RuntimeError("no earlier bundle to go back to")
        self.history.pop()
        return self.live
