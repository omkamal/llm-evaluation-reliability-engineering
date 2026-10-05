"""A stand-in for a model-based injection screen: a toy classifier that
scores a message by how many of five cue families it contains. Real
classifiers are learned and generalise further; what they share with
this one is a boundary, and a boundary can be probed. Illustrative."""
import re

FAMILIES = {
    "authority": {"supervisor", "manager", "management", "lead", "team",
                  "finance", "admin", "colleague", "escalation",
                  "escalations"},
    "approval": {"approved", "agreed", "confirmed", "authorised",
                 "promised", "discussed", "already"},
    "money": {"refund", "credit", "reimburse", "compensation", "payment",
              "adjustment", "goodwill", "courtesy", "return", "funds"},
    "other account": {"other", "second", "another"},
    "skip checks": {"verification", "verify", "verified", "identity",
                    "checks", "skip"},
}


def families(text):
    """Which cue families appear in the text."""
    seen = set(re.findall(r"[a-z]+", text.lower()))
    return {name for name, cues in FAMILIES.items() if seen & cues}


def make_screen(min_families):
    """A screen returns True when a text shows at least this many of the
    five cue families. Lower is stricter."""
    return lambda text: len(families(text)) >= min_families
