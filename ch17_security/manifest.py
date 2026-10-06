"""Pin the tools a server offers. A tool definition is text the model
(or a person approving a call) reads, so a changed definition is a
changed instruction: review it like code, and refuse to run what no one
has reviewed. A pin is not trust: a pinned tool's RESULTS are still
untrusted input, like any order note."""
import hashlib
import json


def fingerprint(tool):
    """The full SHA-256 of everything the server says about one tool:
    name, title, description, inputSchema, outputSchema, annotations,
    and any field added later. Change any of it and the pin breaks."""
    raw = json.dumps(tool, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


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
