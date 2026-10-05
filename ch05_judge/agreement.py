"""Does a judge agree with people? Confusion counts, Cohen's kappa, etc.

Signatures here are shared with later chapters (7 and 8): keep them
stable.
"""
from collections import Counter


def confusion(judge, expert, positive="pass"):
    """(tp, fp, fn, tn) treating `expert` as the truth."""
    pairs = list(zip(judge, expert))
    tp = sum(j == positive and e == positive for j, e in pairs)
    fp = sum(j == positive and e != positive for j, e in pairs)
    fn = sum(j != positive and e == positive for j, e in pairs)
    tn = sum(j != positive and e != positive for j, e in pairs)
    return tp, fp, fn, tn


def labels_from_matrix(tp, fp, fn, tn):
    """Rebuild two label lists (judge, expert) from the four counts."""
    judge = ["pass"] * (tp + fp) + ["fail"] * (fn + tn)
    expert = (["pass"] * tp + ["fail"] * fp
              + ["pass"] * fn + ["fail"] * tn)
    return judge, expert


def observed_agreement(a, b):
    """The share of items where the two raters said the same thing."""
    return sum(x == y for x, y in zip(a, b)) / len(a)


def chance_agreement(a, b):
    """Agreement expected if both raters labelled independently, each at
    its own rate."""
    n = len(a)
    ca, cb = Counter(a), Counter(b)
    return sum((ca[label] / n) * (cb[label] / n)
               for label in set(ca) | set(cb))


def cohen_kappa(a, b):
    """Agreement beyond chance, as a share of the most possible."""
    po, pe = observed_agreement(a, b), chance_agreement(a, b)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def tpr_tnr(judge, expert, positive="pass"):
    """Of the expert's passes, how many did the judge pass (TPR); of the
    expert's fails, how many did it fail (TNR)."""
    tp, fp, fn, tn = confusion(judge, expert, positive)
    return (tp / (tp + fn) if tp + fn else 0.0,
            tn / (tn + fp) if tn + fp else 0.0)


def landis_koch(kappa):
    """Words for a kappa value (Landis and Koch, 1977)."""
    for limit, word in ((0.0, "poor"), (0.20, "slight"), (0.40, "fair"),
                        (0.60, "moderate"), (0.80, "substantial")):
        if kappa <= limit:
            return word
    return "almost perfect"
