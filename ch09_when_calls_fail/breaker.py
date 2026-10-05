"""A small circuit breaker: closed -> open after N failures -> half-open after a cooldown -> closed."""
from common.clock import SystemClock


class CircuitBreaker:
    def __init__(self, threshold=5, cooldown=30.0, probes=3, clock=None):
        self.threshold, self.cooldown = threshold, cooldown
        self.probes = probes
        self.clock = clock or SystemClock()
        self.state, self.failures, self.opened_at = "closed", 0, 0.0
        self.trials = self.passed = 0

    def allow(self):
        waited = self.clock.now() - self.opened_at
        if self.state == "open" and waited >= self.cooldown:
            self.state, self.trials, self.passed = "half_open", 0, 0
        if self.state == "half_open" and self.trials < self.probes:
            self.trials += 1
            return True                       # one of the few controlled probes
        return self.state == "closed"

    def record(self, ok):
        if not ok:
            self.failures += 1
            tripped = self.failures >= self.threshold
            if self.state == "half_open" or tripped:
                self.state, self.opened_at = "open", self.clock.now()
        elif self.state == "half_open":
            self.passed += 1
            if self.passed == self.probes:
                self.state, self.failures = "closed", 0
        else:
            self.failures = 0
