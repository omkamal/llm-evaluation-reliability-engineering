"""Resolved is a claim. Prove it with the suite and with the bands."""
from ch13_drift.bands import check_rate


def failing_cases(config, suite):
    """Names of the regression cases that fail on what is live."""
    return [name for name, case in suite.items() if not case(config)]


def settled(base_p, windows, k=2):
    """True when the last k windows all sit inside the baseline band.
    A window with too little data is not 'inside': it is a skip."""
    states = [check_rate(base_p, good, n) for good, n in windows[-k:]]
    return len(states) == k and all(s == "inside" for s in states)


def can_close(config, suite, signals, k=2):
    """(closed, what is still in the way). `signals` maps a name to
    (baseline rate, [(count, n), ...]), one pair per window."""
    why = [f"{name} fails" for name in failing_cases(config, suite)]
    for name, (base_p, windows) in signals.items():
        if not settled(base_p, windows, k):
            why.append(f"{name} out of band")
    return not why, why
