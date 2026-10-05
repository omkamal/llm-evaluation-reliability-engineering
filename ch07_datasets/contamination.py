"""Do any test cases appear inside the prompt or the judge's examples?"""
import re


def words(text):
    """Lower case, punctuation ignored."""
    return re.findall(r"[a-z0-9$']+", text.lower())


def grams(tokens, n):
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def overlap(case_text, reference_text, n=4):
    """Share of the case's n-grams that also appear in the reference."""
    mine = words(case_text)
    n = min(n, len(mine))           # a short message is checked whole
    ours = grams(mine, n)
    return len(ours & grams(words(reference_text), n)) / len(ours)


def find_leaks(cases, references, n=4, threshold=0.5):
    """(case id, reference name, overlap) for every suspicious pair."""
    leaks = []
    for case in cases:
        for name, ref in references.items():
            share = overlap(case["text"], ref, n)
            if share >= threshold:
                leaks.append((case["id"], name, share))
    return leaks
