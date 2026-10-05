"""The online sample feeds the baseline (Chapter 7's 5% sample)."""
from collections import defaultdict

from ch07_datasets.sampling import in_online_sample, score_record


def judged_by_segment(conversations):
    """Per segment: [judged, good]; failures go to the review queue."""
    counts = defaultdict(lambda: [0, 0])
    queue = []
    for conv in conversations:
        if not in_online_sample(conv["id"]):      # same id, same answer
            continue
        record = score_record(conv["id"], conv["verdict"])
        seen = counts[conv["segment"]]
        seen[0] += 1
        seen[1] += record["verdict"] == "pass"
        if record["verdict"] == "fail":
            queue.append((conv["segment"], record["trace_id"]))
    return counts, queue
