"""Simulated rubric scores for a prompt change, 200 cases, 1 to 5.

ILLUSTRATIVE data, not a measurement. The seed is the one that gives
the chapter's figure: a lift of +0.12, paired interval [+0.03, +0.21]
and unpaired interval [-0.07, +0.31]. Every case has its own difficulty,
shared by both prompts: that sharing is why pairing helps.
"""
import random

SEED = 2950


def clip(score):
    return min(5, max(1, round(score)))


def prompt_ab_scores(n=200, seed=SEED):
    """Return (old_scores, new_scores) for the same n cases."""
    rng = random.Random(seed)
    old, new = [], []
    for _ in range(n):
        ease = rng.gauss(0, 1)                  # this case's difficulty
        before = 3.6 + 0.9 * ease + rng.gauss(0, 0.55)
        after = before + 0.25 + rng.gauss(0, 0.55)  # the new prompt helps
        old.append(clip(before))
        new.append(clip(after))
    return old, new
