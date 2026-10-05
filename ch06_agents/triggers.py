"""The two by two of trigger cases: should it act, and did it act?"""


def did_act(run):
    """Did the world change? Read from the audit log, not the reply."""
    return bool(run["after"]["audit_log"])


def cell(should_act, acted):
    if should_act:
        return "correct trigger" if acted else "missed trigger"
    return "false trigger" if acted else "correct non-trigger"


def trigger_rates(pairs):
    """pairs: [(should_act, did_act), ...]. Returns the two error rates
    separately, plus the blended accuracy that hides them. A rate is None
    when the suite has no cases to measure it on."""
    should = [acted for s, acted in pairs if s]
    should_not = [acted for s, acted in pairs if not s]
    wrong = sum(1 for s, a in pairs if s != a)
    return {
        "missed": should.count(False) / len(should) if should else None,
        "false": should_not.count(True) / len(should_not)
        if should_not else None,
        "accuracy": 1 - wrong / len(pairs),
    }
