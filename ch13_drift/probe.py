"""Drift-probe sets: a small fixed set you re-run to see what changed.

Two things drift without a line of your code changing: the model behind a
floating name, and the judge that grades your answers. Both get the same
treatment: re-run a fixed set, compare with a band from an A/A check.
All pass chances below are ILLUSTRATIVE.
"""
import random
from collections import Counter

from ch05_judge.agreement import cohen_kappa
from ch13_drift.bands import noise_band

TOPICS = ["returns", "refund-timing", "damaged", "reschedule",
          "delivery-windows", "lost-parcel", "refund-approval",
          "address-change", "free-shipping", "support-hours"]
CASES = [(f"{t}-{i}", t) for t in TOPICS for i in range(1, 5)]   # 40

ALIAS = "a-large-latest"       # a floating name the provider repoints
CHANCE = {                     # chance a snapshot passes a topic's cases
    "a-large-v1": {t: 0.96 for t in TOPICS},
    "a-large-v2": {**{t: 0.96 for t in TOPICS}, "returns": 0.45,
                   "refund-timing": 0.55, "damaged": 0.70,
                   "lost-parcel": 0.60},
}


def snapshot_behind(model, day, repoint_day):
    """Which snapshot answers today. The alias moves; a pin never does."""
    if model != ALIAS:
        return model
    return "a-large-v1" if day < repoint_day else "a-large-v2"


def run_probe(snapshot, rng):
    """One run of the 40 fixed cases: (score, ids of failed cases)."""
    failed = [cid for cid, topic in CASES
              if rng.random() >= CHANCE[snapshot][topic]]
    return 1 - len(failed) / len(CASES), failed


def flipped_topics(failed_before, failed_after):
    """Topics that fail more often after the change, with counts."""
    topic = dict(CASES)
    before = Counter(topic[c] for c in failed_before)
    after = Counter(topic[c] for c in failed_after)
    return {t: after[t] - before[t] for t in TOPICS
            if after[t] > before[t]}


# ---- the judge is a model too ------------------------------------------

EXPERT = ["pass"] * 78 + ["fail"] * 42        # Chapter 5's held-out labels


def rerun_judge(tpr, tnr, rng):
    """Re-run the held-out set; the judge agrees by chance tpr or tnr."""
    verdicts = []
    for label in EXPERT:
        agree = rng.random() < (tpr if label == "pass" else tnr)
        verdicts.append(label if agree else
                        "fail" if label == "pass" else "pass")
    return verdicts


def judged_rate(true_rate, tpr, tnr):
    """The good-answer rate a judge reports for a given true rate."""
    return true_rate * tpr + (1 - true_rate) * (1 - tnr)


def monthly_kappa(months, change_month, seed=0):
    """Kappa each month; the provider swaps the judge's model."""
    rng = random.Random(seed)
    out = []
    for m in range(1, months + 1):
        tnr = 0.92 if m < change_month else 0.70
        out.append(cohen_kappa(rerun_judge(0.93, tnr, rng), EXPERT))
    return out


def judge_band(runs=5, seed=1):
    """A/A band: re-run the unchanged judge a few times on day one."""
    rng = random.Random(seed)
    return noise_band([cohen_kappa(rerun_judge(0.93, 0.92, rng), EXPERT)
                       for _ in range(runs)])
