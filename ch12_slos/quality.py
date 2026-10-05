"""Quality SLIs: a judged sample, refusals, and cost per success."""
from ch04_numbers.stats import proportion_ci


def judge_verdict(passes, n, target):
    """Pass rate with its 95% interval, and a verdict against the SLO."""
    rate, _, (lo, hi) = proportion_ci(passes, n)
    if lo >= target:
        verdict = "met"
    elif hi < target:
        verdict = "missed"
    else:
        verdict = "unclear"        # the interval straddles the line
    return rate, (lo, hi), verdict


def judge_reading(true_rate, tpr, tnr):
    """The pass rate a judge REPORTS when the true rate is `true_rate`.

    A judge passes good answers with probability TPR and wrongly passes
    bad ones with probability 1 - TNR (Chapter 5).
    """
    return true_rate * tpr + (1 - true_rate) * (1 - tnr)


def refusal_rate(replies, markers=("i can't help", "i cannot help")):
    """Share of replies that decline. A code check, on all traffic."""
    refused = sum(any(m in r.lower() for m in markers) for r in replies)
    return refused / len(replies)


def cost_per_success(total_usd, successes):
    """Every dollar spent, retries and failures included, per success."""
    return total_usd / successes
