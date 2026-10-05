"""A latency waterfall: when does each step start and end?"""
from dataclasses import dataclass

FIRST_TOKEN = 0.4     # seconds from an answer's start to its first word


@dataclass(frozen=True)
class Step:
    name: str
    seconds: float
    after: tuple = ()      # names of the steps that must finish first


def schedule(steps):
    """{name: (start, end)}; steps are listed after their dependencies."""
    when = {}
    for s in steps:
        start = max((when[d][1] for d in s.after), default=0.0)
        when[s.name] = (start, round(start + s.seconds, 2))
    return when


def critical_path(steps):
    """The chain of steps that sets the total: the ones to speed up."""
    when, by_name = schedule(steps), {s.name: s for s in steps}
    name = max(when, key=lambda n: when[n][1])
    path = [name]
    while by_name[path[-1]].after:
        last = by_name[path[-1]].after
        path.append(max(last, key=lambda d: when[d][1]))
    return path[::-1]


def sequential():
    return [Step("plan", 1.2), Step("track", 0.8, ("plan",)),
            Step("search", 0.9, ("track",)),
            Step("answer", 2.4, ("search",))]


def parallel():
    return [Step("plan", 1.2), Step("track", 0.8, ("plan",)),
            Step("search", 0.9, ("plan",)),
            Step("answer", 2.4, ("track", "search"))]


def first_words(steps):
    """With streaming the customer sees words at the answer's start
    plus the time to first token, not at its end."""
    return round(schedule(steps)["answer"][0] + FIRST_TOKEN, 2)


def waterfall(steps, per_second=10):
    """One row per step, a bar for each, as text."""
    rows = []
    for name, (start, end) in schedule(steps).items():
        pad = " " * round(start * per_second)
        bar = "#" * round((end - start) * per_second)
        rows.append(f"{name:<7}|{pad}{bar}")
    return rows
