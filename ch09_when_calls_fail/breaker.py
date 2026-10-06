"""A small circuit breaker: closed -> open after N failures -> half-open after a cooldown -> closed.

Every call that allow() lets through must call record() exactly once, in a `finally` block,
with a timeout or exception counted as a failure, and with the ticket allow() returned."""
from common.clock import SystemClock


class CircuitBreaker:
    def __init__(self, threshold=5, cooldown=30.0, probes=3, clock=None):
        if threshold < 1 or probes < 1:
            raise ValueError("threshold and probes must be at least 1")
        self.threshold, self.cooldown = threshold, cooldown
        self.probes = probes
        self.clock = clock or SystemClock()
        self.state, self.failures, self.since = "closed", 0, 0.0
        self.trials = self.passed = 0

    def allow(self):
        """True for a normal call, "probe" for a half-open test call, False to fail fast."""
        waited = self.clock.now() - self.since
        if self.state == "half_open" and waited >= self.cooldown:
            self._open()                      # a silent probe failed
        elif self.state == "open" and waited >= self.cooldown:
            self.state, self.since = "half_open", self.clock.now()
            self.trials = self.passed = 0
        if self.state == "half_open" and self.trials < self.probes:
            self.trials += 1
            return "probe"                    # one of the few test calls
        return self.state == "closed"

    def record(self, ok, ticket=True):
        if self.state == "half_open" and ticket != "probe":
            return                            # late result from before
        if not ok:
            self.failures += 1
            tripped = self.failures >= self.threshold
            if self.state == "half_open" or tripped:
                self._open()
        elif self.state == "half_open":
            self.passed += 1
            if self.passed == self.probes:
                self.state, self.failures = "closed", 0
        else:
            self.failures = 0

    def _open(self):
        self.state, self.since = "open", self.clock.now()

    @property
    def opened_at(self):                      # the old name, kept for compatibility
        return self.since
