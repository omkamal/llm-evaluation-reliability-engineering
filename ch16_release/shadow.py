"""Shadow testing: the new version sees live chats, nobody sees its answers.

Both versions answer the SAME chat, so the comparison is paired
(Chapter 4): each chat is compared with itself.
"""
from dataclasses import dataclass

from ch04_numbers.stats import paired_bootstrap, sign_test_p


@dataclass
class ShadowReport:
    n: int
    old_rate: float
    new_rate: float
    diff: float                 # new minus old, paired
    interval: tuple
    disagree: float             # share of chats where they differ
    worse: int                  # old fine, new bad
    better: int                 # old bad, new fine
    p_flips: float              # sign test on those changed chats
    examples: list              # chat ids to read first


def shadow(chats, old, new, flag, resamples=2000):
    """Serve `old`; run `new` beside it; compare one bad-flag per chat."""
    pairs = []
    for chat in chats:
        a = getattr(old.serve(chat), flag)    # what customers get
        b = getattr(new.serve(chat), flag)    # what we only record
        if a is not None and b is not None:   # both versions graded
            pairs.append((chat.id, int(a), int(b)))
    old_bad, new_bad = [p[1] for p in pairs], [p[2] for p in pairs]
    diff, interval = paired_bootstrap(old_bad, new_bad, seed=1,
                                      resamples=resamples)
    worse = sum(1 for _, a, b in pairs if b > a)
    better = sum(1 for _, a, b in pairs if b < a)
    return ShadowReport(
        len(pairs), sum(old_bad) / len(pairs), sum(new_bad) / len(pairs),
        diff, interval, (worse + better) / len(pairs), worse, better,
        sign_test_p(better, worse),
        [i for i, a, b in pairs if a != b][:3])
