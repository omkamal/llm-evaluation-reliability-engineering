"""Truncation or schema design? A triage you can automate."""
from collections import Counter


def balanced(text):
    """True if every bracket and brace that was opened was also closed (ignoring strings)."""
    depth, in_str, esc = 0, False, False
    for ch in text:
        if in_str:
            esc = (ch == "\\") and not esc
            if ch == '"' and not esc:
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
    return depth == 0 and not in_str


def classify(reply_text, finish_reason, output_tokens, max_tokens):
    """First question: did the output run out of room?"""
    if (finish_reason == "length" or output_tokens >= max_tokens
            or not balanced(reply_text)):
        return "truncation"   # fix the budget, not the repair loop
    return "validation"          # complete JSON that broke a rule


def schema_suspects(quarantined, min_share=0.5):
    """Second question: does one field fail across many outputs?"""
    failing = Counter()
    for q in quarantined:
        names = {loc.split(".")[0] for loc, *_ in q.errors if loc}
        for name in names:
            failing[name] += 1
    return {name: n for name, n in failing.items()
            if n >= min_share * len(quarantined)}
