"""Double-labeling with an adjudicator, simulated (illustrative numbers).

Every item has a truth only the simulation knows. An annotator labels it
correctly 97% of the time, except where the guideline is silent: then the
label is a coin flip between two readings.
"""
import random
from collections import Counter

from ch05_judge.agreement import cohen_kappa, observed_agreement

MOVES = ("answer", "act", "clarify", "hand_off")
KINDS = [("plain", 0.60), ("late parcel", 0.15),
         ("next friday", 0.13), ("credit demand", 0.12)]
SILENT = ("late parcel", "next friday", "credit demand")
SLIP = 0.03


def make_items(n=100, seed=3):
    rng = random.Random(seed)
    kinds, weights = zip(*KINDS)
    items = []
    for i in range(n):
        truth = rng.choice(MOVES)
        other = rng.choice([m for m in MOVES if m != truth])
        items.append({"id": i, "kind": rng.choices(kinds, weights)[0],
                      "truth": truth, "other": other})
    return items


def label(item, guideline, rng):
    """One annotator's label. Guideline v1 is silent on three kinds."""
    if guideline == 1 and item["kind"] in SILENT:
        return item["truth"] if rng.random() < 0.5 else item["other"]
    if rng.random() < SLIP:
        return rng.choice([m for m in MOVES if m != item["truth"]])
    return item["truth"]


def double_label(items, guideline, seed=5):
    """A and B label alone; the adjudicator settles each disagreement."""
    rng = random.Random(seed)
    a = [label(i, guideline, rng) for i in items]
    b = [label(i, guideline, rng) for i in items]
    # The adjudicator owns the policy, so the gap in v1 is not theirs.
    final = [x if x == y else label(i, 2, rng)
             for i, x, y in zip(items, a, b)]
    return a, b, final


def summary(items, guideline):
    a, b, final = double_label(items, guideline)
    truth = [i["truth"] for i in items]
    split = Counter(i["kind"] for i, x, y in zip(items, a, b) if x != y)
    return {
        "agreement": observed_agreement(a, b),
        "kappa": cohen_kappa(a, b),
        "disagreements": dict(sorted(split.items())),
        "adjudicated": sum(x != y for x, y in zip(a, b)),
        "final_right": observed_agreement(final, truth),
        "agreed_wrong": sum(x == y != t for x, y, t in zip(a, b, truth)),
    }


def majority_right(guideline, labelers, trials=2000, seed=11):
    """How often a vote of `labelers` gets a rule-less item right."""
    rng = random.Random(seed)
    item = {"kind": "late parcel", "truth": "answer", "other": "act"}
    right = 0
    for _ in range(trials):
        votes = Counter(label(item, guideline, rng)
                        for _ in range(labelers))
        right += votes.most_common(1)[0][0] == item["truth"]
    return right / trials
