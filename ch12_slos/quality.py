"""Quality SLIs: a judged sample, refusals, and cost per success."""
from ch04_numbers.stats import wilson_interval


def judge_reading(true_rate, tpr, tnr):
    """The pass rate a judge REPORTS when the true rate is `true_rate`.

    A judge passes good answers with probability TPR and wrongly passes
    bad ones with probability 1 - TNR (Chapter 5).
    """
    return true_rate * tpr + (1 - true_rate) * (1 - tnr)


def judge_corrected(reading, tpr, tnr):
    """The true pass rate behind a reading: judge_reading, undone.

    This is the Rogan-Gladen correction. It is only as good as the TPR
    and TNR you measured, and a judge with TPR + TNR <= 1 tells good
    from bad no better than a coin, so nothing can be recovered.
    """
    separation = tpr + tnr - 1
    if separation <= 0:
        raise ValueError("this judge cannot tell good answers from bad")
    return min(1.0, max(0.0, (reading + tnr - 1) / separation))


def judge_verdict(passes, n, target, tpr=1.0, tnr=1.0):
    """Pass rate with its 95% interval, and a verdict against the SLO.

    With the defaults the judge is taken at its word. Given its TPR and
    TNR, the rate and both ends of the interval are corrected first,
    which widens the interval by 1 / (TPR + TNR - 1).
    """
    lo, hi = wilson_interval(passes, n)
    rate, lo, hi = (judge_corrected(x, tpr, tnr)
                    for x in (passes / n, lo, hi))
    if lo >= target:
        verdict = "met"
    elif hi < target:
        verdict = "missed"
    else:
        verdict = "unclear"        # the interval straddles the line
    return rate, (lo, hi), verdict


def daily_reads(good_rates, per_day, target, days=7):
    """Read the last `days` days every morning: one verdict per day.

    `good_rates` holds one true good rate per day, oldest first; each
    day adds its expected passes, so the replay has no luck in it.
    """
    passes = [round(r * per_day) for r in good_rates]
    return [judge_verdict(sum(passes[end - days:end]), per_day * days,
                          target)[2]
            for end in range(days, len(passes) + 1)]


def refusal_rate(replies, markers=("i can't help", "i cannot help")):
    """Share of replies that decline. A code check, on all traffic."""
    refused = sum(any(m in r.lower() for m in markers) for r in replies)
    return refused / len(replies)


def cost_per_success(total_usd, successes):
    """Every dollar spent, retries and failures included, per success."""
    return total_usd / successes
