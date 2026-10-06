"""Status updates: one template, four parts, and a lint for what an
update must not say. The lint is a checklist, not a writer."""
import re
import textwrap
from dataclasses import dataclass

GUESS = re.compile(r"\b(probably|maybe|perhaps|we think|we believe|"
                   r"might have|seems to)\b", re.I)
PROMISE = re.compile(r"will be (fixed|resolved|restored|back)|\bETA\b",
                     re.I)
BLAME = re.compile(r"human error|careless|mistake by|fault of", re.I)
DONE = re.compile(r"\b(is|has been|are now|now) (resolved|fixed|"
                  r"restored)\b", re.I)
# "no other ... affected" is a guess until the check has run
ALL_CLEAR = re.compile(r"\bno (one|other|further)\b[^.]*\baffected\b",
                       re.I)
# words a customer should never need to read
JARGON = ("SEV", "prompt", "injection", "bundle", "flag", "model",
          "guardrail", "kill switch", "tool call")


@dataclass(frozen=True)
class StatusUpdate:
    what: str        # what happened, one plain sentence
    who: str         # who is affected, and who is not
    doing: str       # what we are doing about it
    next_at: str     # when the next update arrives

    def text(self):
        parts = (("What happened", self.what),
                 ("Who is affected", self.who),
                 ("What we are doing", self.doing),
                 ("Next update", self.next_at))
        return "\n".join(textwrap.fill(f"{name}: {body}", 70,
                                       subsequent_indent="  ")
                         for name, body in parts)


def lint(update, audience, people=(), verified=False):
    """Problems to fix before sending. audience: internal | customer."""
    text, out = update.text(), []
    if not update.next_at.strip():
        out.append("no time for the next update")
    if GUESS.search(text):
        out.append("guesses at the cause")
    if PROMISE.search(text):
        out.append("promises a fix time")
    if BLAME.search(text) or any(p in text for p in people):
        out.append("points at a person")
    if DONE.search(text) and not verified:
        out.append("says fixed before recovery is verified")
    if ALL_CLEAR.search(text) and not verified:
        out.append("rules others out before the check is done")
    if audience == "customer":
        words = [w for w in JARGON if w.lower() in text.lower()]
        if words:
            out.append("internal words: " + ", ".join(words))
    return out
