"""What leaves the building. Check an outbound prompt, a log line or a
trace attribute for secrets and personal data before it is sent."""
import re

from ch07_datasets.redact import redact

# key-shaped strings; "relay_live_" is an invented prefix
SECRETS = [
    ("API_KEY", re.compile(r"\brelay_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("BEARER", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}")),
]


class SecretInPrompt(Exception):
    pass


def find_secrets(text):
    """Kinds of secret found, with counts. Never returns the secret."""
    found = {}
    for kind, pattern in SECRETS:
        hits = pattern.findall(text)
        if hits:
            found[kind] = len(hits)
    return found


def guard_prompt(text):
    """Fail fast: a prompt with a key in it is never sent."""
    found = find_secrets(text)
    if found:
        kinds = ", ".join(f"{k} x{n}" for k, n in found.items())
        raise SecretInPrompt(kinds)
    return text


def scrub(text):
    """For logs and traces: secrets are masked, personal data is
    replaced with placeholders by Chapter 7's redactor."""
    for kind, pattern in SECRETS:
        text = pattern.sub(f"<{kind}>", text)
    return redact(text)[0]
