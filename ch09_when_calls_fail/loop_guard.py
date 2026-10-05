"""Catch an agent that repeats itself: a step cap plus repeated-action detection."""
from collections import Counter

MAX_STEPS = 12          # hard cap on steps per task
MAX_REPEATS = 3         # the same tool with the same arguments


class LoopGuard:
    def __init__(self):
        self.steps, self.seen = 0, Counter()

    def check(self, tool, args):
        self.steps += 1
        key = (tool, tuple(sorted(args.items())))
        self.seen[key] += 1
        if self.steps > MAX_STEPS:
            raise RuntimeError(f"step cap hit after {MAX_STEPS} steps")
        if self.seen[key] > MAX_REPEATS:
            raise RuntimeError(
                f"loop: {tool} x{self.seen[key]}, same args")
