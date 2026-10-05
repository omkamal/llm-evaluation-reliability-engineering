"""A model's life: notice, migration plan, retirement."""
# (step, share of the notice window by which it must be done)
RUNBOOK = (
    ("scorecard on our own eval set", 0.10),
    ("eval gate passed on the new snapshot", 0.25),
    ("shadow on live traffic", 0.40),
    ("canary release starts", 0.55),
    ("full rollout done", 0.75),
    ("old model kept only as a rollback target", 0.90),
)


def notice_days(notified, retires):
    """Days between the notice and the retirement date."""
    return (retires - notified).days


def migration_plan(window_days):
    """[(day, step)] counted from the day the notice arrives."""
    return [(round(window_days * share), step) for step, share in RUNBOOK]


def days_left(today, retires):
    return (retires - today).days


def retirement_alarm(today, retires, plan_days=45):
    """Fire when less time is left than a migration needs."""
    left = days_left(today, retires)
    if left < plan_days:
        return f"{left} days to retirement; a migration needs {plan_days}"
    return None
