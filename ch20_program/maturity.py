"""Where a feature really stands on the five-step maturity ladder.

A level is the highest step whose controls are ALL in place, with every
step below it. Tools bought do not count; controls that work do.
"""

LEVELS = ("Vibes", "Guarded", "Measured", "Operated", "Governed")

# Four telling controls per level, and the chapter that teaches each.
CONTROLS = {
    1: (("validated output", 2), ("tool tiers and contracts", 2),
        ("idempotent writes", 2), ("one log line per call", 1)),
    2: (("eval set from real failures", 3), ("intervals on scores", 4),
        ("calibrated judge", 5), ("state check on the riskiest tool", 6)),
    3: (("SLO sheet and burn-rate pages", 12),
        ("bounded retries and budgets", 9), ("traces", 11),
        ("eval gate and staged releases", 15)),
    4: (("one accountable owner per item", 20),
        ("scoped credentials and review line", 18),
        ("kill switch and pin, drilled", 19),
        ("readiness review each quarter", 20)),
}


def place(have):
    """The level reached, and the controls that stop the next one."""
    level = 0
    for step in (1, 2, 3, 4):
        if any(name not in have for name, _ in CONTROLS[step]):
            break
        level = step
    if level == 4:
        return level, []
    missing = [(name, ch) for name, ch in CONTROLS[level + 1]
               if name not in have]
    return level, missing
