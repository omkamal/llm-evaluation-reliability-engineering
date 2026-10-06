"""Implicit feedback: hints that a conversation went wrong. Not verdicts."""
import re

HUMAN_ASKS = ("real person", "human", "speak to someone", "talk to a person")


def words(text):
    return set(re.findall(r"[a-z0-9-]+", text.lower()))


def similar(a, b):
    """Jaccard overlap of the words: how alike two messages are."""
    wa, wb = words(a), words(b)
    if not wa | wb:                 # two wordless turns, such as "??"
        return 0.0
    return len(wa & wb) / len(wa | wb)


def hints(conv):
    """The hints found in one conversation: a list of short names."""
    found = []
    said = [t["text"] for t in conv["turns"] if t["who"] == "customer"]
    if any(similar(x, y) >= 0.5 for x, y in zip(said, said[1:])):
        found.append("rephrased")
    if any(ask in text.lower() for text in said for ask in HUMAN_ASKS):
        found.append("asked_for_human")
    back = conv.get("reopened_after_hours")
    if back is not None and back <= 48:
        found.append("reopened_48h")
    return found


def thumbs_share(quality, up_if_good, down_if_bad):
    """(share of ratings that are thumbs-up, share of people who rated)."""
    up = quality * up_if_good
    down = (1 - quality) * down_if_bad
    return up / (up + down), up + down
