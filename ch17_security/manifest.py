"""Pin the tools a server offers. A tool description is text the model
reads, so a changed description is a changed instruction: review it like
code, and refuse to run what no one has reviewed."""
import hashlib
import json


def fingerprint(tool):
    """A short hash of everything the model sees about one tool."""
    shown = {k: tool[k] for k in ("name", "description", "schema")}
    raw = json.dumps(shown, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:12]


def pin(tools):
    """Record the reviewed manifest: tool name to fingerprint."""
    return {t["name"]: fingerprint(t) for t in tools}


def drift(tools, pins):
    """How a server's offer differs from what was pinned."""
    now = pin(tools)
    found = [(name, "changed") for name, fp in now.items()
             if name in pins and pins[name] != fp]
    found += [(name, "new") for name in now if name not in pins]
    found += [(name, "gone") for name in pins if name not in now]
    return sorted(found)
