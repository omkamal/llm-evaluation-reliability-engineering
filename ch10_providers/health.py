"""Health signals the adapters already see, over a sliding window."""
from collections import deque
from math import ceil

SLOW = 5.0        # seconds to first token that score zero for speed


class HealthWindow:
    """Outcomes and first-token times for one provider, last 5 minutes."""

    def __init__(self, clock, window=300.0, min_samples=20):
        self.clock, self.window = clock, window
        self.min_samples = min_samples
        self.samples = deque()           # (time, ok, first-token seconds)

    def record(self, ok, ttft=None):
        self.samples.append((self.clock.now(), ok, ttft))

    def recent(self):
        cutoff = self.clock.now() - self.window
        while self.samples and self.samples[0][0] < cutoff:
            self.samples.popleft()       # old news is not health
        return self.samples

    def success(self):
        recent = self.recent()
        if len(recent) < self.min_samples:
            return 0.5                   # too little data: stay neutral
        return sum(ok for _, ok, _ in recent) / len(recent)

    def ttft_p95(self):
        times = sorted(t for _, ok, t in self.recent() if ok and t)
        if not times:
            return SLOW                  # no evidence of speed
        return times[ceil(0.95 * len(times)) - 1]
