"""A context window is a budget. When it overflows, something is silently dropped."""
from ch01_anatomy.call import count_tokens


def fit_to_window(turns, window_tokens):
    """Keep the system prompt and the newest turns; drop the oldest first.
    Returns (kept, dropped) so that a drop is never silent."""
    system, rest = turns[0], turns[1:]
    kept, used = [], count_tokens(system)
    for turn in reversed(rest):                 # newest first
        need = count_tokens(turn)
        if used + need > window_tokens:
            break
        kept.insert(0, turn)
        used += need
    dropped = rest[: len(rest) - len(kept)]
    return [system] + kept, dropped
