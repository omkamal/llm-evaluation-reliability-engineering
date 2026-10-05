"""Pool the votes of several judges (Chapter 5)."""
from statistics import mean, median


def aggregate(scores, how="mean", weights=None, passing=4):
    """One verdict from several 1-5 scores.

    mean and median pool the scores; majority pools the pass/fail votes;
    weighted pools scores by how well each judge agrees with people.
    """
    if how == "mean":
        return mean(scores)
    if how == "median":
        return median(scores)
    if how == "majority":
        passes = sum(s >= passing for s in scores)
        return "pass" if passes * 2 > len(scores) else "fail"
    if how == "weighted":
        return sum(w * s for w, s in zip(weights, scores)) / sum(weights)
    raise ValueError(f"unknown aggregator: {how}")


def needs_a_person(scores, line=3.5, band=0.25):
    """True when the average sits close to the pass line: the cases a
    jury is least sure about. Send these to a human."""
    return abs(mean(scores) - line) <= band
