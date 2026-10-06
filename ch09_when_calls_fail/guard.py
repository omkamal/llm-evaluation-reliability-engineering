"""Check four budgets BEFORE every agent step (a prepaid card, not a monthly statement).

The step budgets belong to ONE task (one customer request and the agent steps it sets off):
make a new StepGuard for every task, not one per conversation."""
import threading

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
        self.lock = threading.Lock()    # check and reserve as one act

    def before_step(self, est_tokens, est_usd):
        need = {"steps": 1, "tokens": est_tokens, "usd": est_usd,
                "seconds": 0}
        with self.lock:
            self.used["seconds"] = self.clock.now() - self.start
            for k, extra in need.items():     # so 3 x $0.10 fits $0.30
                if round(self.used[k] + extra, 6) > self.limit[k]:
                    raise BudgetExceeded(
                        f"{k}: limit {self.limit[k]} reached")
            for k, extra in need.items():   # reserve before the step runs
                self.used[k] += extra
