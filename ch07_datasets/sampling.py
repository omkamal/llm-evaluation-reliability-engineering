"""Two samplers for two jobs: coverage for datasets, rates for monitoring."""
import hashlib
import random
from collections import defaultdict

KEYS = ("channel", "region", "task")


def stratum(row, keys=KEYS):
    return tuple(row[k] for k in keys)


def coverage(rows, keys=KEYS):
    """How many different (channel, region, task) groups are present."""
    return len({stratum(r, keys) for r in rows})


def random_sample(log, n, seed=1):
    return random.Random(seed).sample(log, n)


def stratified_sample(log, n, keys=KEYS, seed=1):
    """Take one from each group in turn, so no group is left out."""
    rng = random.Random(seed)
    groups = defaultdict(list)
    for row in log:
        groups[stratum(row, keys)].append(row)
    for rows in groups.values():
        rng.shuffle(rows)
    order = sorted(groups)
    rng.shuffle(order)
    picked = []
    while len(picked) < n and any(groups.values()):
        for key in order:
            if groups[key] and len(picked) < n:
                picked.append(groups[key].pop())
    return picked


def in_online_sample(conversation_id, rate=0.05):
    """Same id, same answer: on any machine, in any order."""
    digest = hashlib.sha256(conversation_id.encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2 ** 64 < rate


def score_record(trace_id, verdict, judge="judge_v2"):
    """What gets stored: the score travels with the trace it grades."""
    return {"trace_id": trace_id, "judge": judge, "verdict": verdict}
