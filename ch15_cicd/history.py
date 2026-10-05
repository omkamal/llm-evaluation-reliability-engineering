"""When a score drops: test the midpoint, not every change."""


def bisect(changes, is_bad):
    """The first change after which the build is bad, and how many evals
    it took. changes[:0] must be good and all of `changes` bad."""
    good, bad = 0, len(changes)
    runs = 0
    while bad - good > 1:
        middle = (good + bad) // 2
        runs += 1
        if is_bad(changes[:middle]):
            bad = middle
        else:
            good = middle
    return changes[bad - 1], runs
