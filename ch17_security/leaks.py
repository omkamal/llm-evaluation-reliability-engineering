"""What leaves the building. Check an outbound prompt, a log line or a
trace attribute for secrets and personal data before it is sent, and a
reply for links before a window renders it."""
import re

from ch07_datasets.redact import redact

# Illustrative patterns: our invented key ("relay_live_") and a few
# common shapes. They miss a key split by a space, or encoded. Real
# scanning needs a maintained detector (provider formats, entropy), and
# it is a backstop: credentials belong in the tool layer.
SECRETS = [
    ("API_KEY", re.compile(r"(?i)(?<![a-z0-9])(?:relay_(?:live|test)_"
                           r"|sk-(?:proj-)?|gh[pousr]_|glpat-)"
                           r"[a-z0-9_-]{12,}")),
    ("AWS_KEY", re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])")),
    ("JWT", re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}")),
    ("BEARER", re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/-]{12,}=*")),
]
# zero-width characters hide inside a key and break every pattern
INVISIBLE = re.compile("[​‌‍⁠﻿]")
# a placeholder glued to letters or digits: the redactor cut into a
# longer token, perhaps a key, so the whole token goes
GLUED = re.compile(r"\S*\w<[A-Z]+_\d+>\S*|\S*<[A-Z]+_\d+>\w\S*")


class SecretInPrompt(Exception):
    pass


def find_secrets(text):
    """Kinds of secret found, with counts. Never returns the secret."""
    text, found = INVISIBLE.sub("", text), {}
    for kind, pattern in SECRETS:
        text, hits = pattern.subn(" ", text)   # count each one once
        if hits:
            found[kind] = hits
    return found


def guard_prompt(text):
    """Fail fast: a prompt with a key in it is never sent. Use it on
    what your own code assembles; mask text a customer wrote (scrub),
    or one planted key would block every prompt that reads it."""
    found = find_secrets(text)
    if found:
        kinds = ", ".join(f"{k} x{n}" for k, n in found.items())
        raise SecretInPrompt(kinds)
    return text


def scrub(text):
    """For logs and traces: secrets are masked whole, personal data is
    replaced with placeholders by Chapter 7's redactor."""
    text = INVISIBLE.sub("", text)
    for kind, pattern in SECRETS:
        text = pattern.sub(f"<{kind}>", text)
    return GLUED.sub("<SECRET>", redact(text)[0])


ALLOWED_HOSTS = {"crateway.example"}         # invented for the book
URL = re.compile(r"(?i)(?:https?:)?[/\\]{2}([^\s/\\?#)\]>\"']+)"
                 r"[^\s)\]>\"']*")


def host(netloc):
    """The host a browser would contact: after any user@, before :port."""
    return netloc.rsplit("@", 1)[-1].split(":")[0].lower()


def safe_reply(text, allowed=ALLOWED_HOSTS):
    """Before a chat window or the staff panel renders a reply: a link
    or image to a host not on the allow-list is removed, so an address
    the model was talked into writing cannot carry data out."""
    def keep(match):
        ok = host(match.group(1)) in allowed
        return match.group(0) if ok else "[link removed]"
    return URL.sub(keep, text)
