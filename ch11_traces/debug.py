"""Debugging with traces: shrink a failing run to a minimal repro."""


def shrink(items, still_fails):
    """Drop one item at a time while the failure persists. The result is
    1-minimal: removing any single item makes the failure go away."""
    items = list(items)
    changed = True
    while changed:
        changed = False
        for i in range(len(items)):
            smaller = items[:i] + items[i + 1:]
            if still_fails(smaller):
                items, changed = smaller, True
                break
    return items
