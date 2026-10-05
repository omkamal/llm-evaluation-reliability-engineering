"""Check four budgets BEFORE every agent step (a prepaid card, not a monthly statement)."""
from common.clock import SystemClock


class BudgetExceeded(Exception):
    pass


class StepGuard:
    def __init__(self, steps=12, tokens=40_000, usd=0.50, seconds=90.0,
                 clock=None):
        self.limit = {"steps": steps, "tokens": tokens, "usd": usd,
                      "seconds": seconds}
        self.used = {"steps": 0, "tokens": 0, "usd": 0.0, "seconds": 0.0}
        self.clock = clock or SystemClock()
        self.start = self.clock.now()

    def before_step(self, est_tokens, est_usd):
        self.used["seconds"] = self.clock.now() - self.start
        need = {"steps": 1, "tokens": est_tokens, "usd": est_usd,
                "seconds": 0}
        for k, extra in need.items():
            if self.used[k] + extra > self.limit[k]:
                raise BudgetExceeded(
                    f"{k}: limit {self.limit[k]} reached")
        for k, extra in need.items():   # reserve before the step runs
            self.used[k] += extra
