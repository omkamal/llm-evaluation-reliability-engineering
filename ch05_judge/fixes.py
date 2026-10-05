"""Checks for a judge's biases, and the fixes (Chapter 5)."""
from collections import Counter
from statistics import mean

from ch05_judge.simjudge import compare, score_of


def winner(cfg, x, y):
    """One call, x listed first. Returns 'x', 'y' or 'tie'."""
    return {"A": "x", "B": "y", "tie": "tie"}[compare(cfg, x, y)]


def swapped(cfg, x, y):
    """Ask twice, once per order. A win needs both orders to agree."""
    one = winner(cfg, x, y)
    two = {"x": "y", "y": "x", "tie": "tie"}[winner(cfg, y, x)]
    return one if one == two else "tie"


def swap_consistency(cfg, pairs):
    """Share of pairs where both orders give the same verdict."""
    same = 0
    for x, y in pairs:
        reversed_ = {"x": "y", "y": "x", "tie": "tie"}[winner(cfg, y, x)]
        same += winner(cfg, x, y) == reversed_
    return same / len(pairs)


def tally(cfg, pairs, swap=False):
    """How often the first-listed answer wins, loses or ties."""
    pick = swapped if swap else winner
    counts = Counter(pick(cfg, x, y) for x, y in pairs)
    return {k: counts[k] / len(pairs) for k in ("x", "y", "tie")}


def length_gap(cfg, answers):
    """Points a judge adds for being longer, at equal true quality.

    Inside each quality level, compare the longer half with the shorter
    half; then average the gaps. An unbiased judge gives about zero.
    """
    gaps = []
    for level in range(1, 6):
        group = sorted((a for a in answers if a.quality == level),
                       key=lambda a: a.words)
        half = len(group) // 2
        if half:
            short, long_ = group[:half], group[-half:]
            gaps.append(mean(score_of(cfg, a) for a in long_)
                        - mean(score_of(cfg, a) for a in short))
    return mean(gaps)


def self_preference_gap(cfg, own, other):
    """Mean score for the judge's own family minus another family's,
    on answers of equal quality."""
    return (mean(score_of(cfg, a) for a in own)
            - mean(score_of(cfg, a) for a in other))
