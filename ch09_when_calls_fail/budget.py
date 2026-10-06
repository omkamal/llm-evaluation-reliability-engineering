"""A shared retry budget: retries may use only about 10% of request volume."""


class RetryBudget:
    def __init__(self, ratio=0.1, burst=5.0):
        if burst < 1:
            raise ValueError("burst must hold at least one whole token")
        self.ratio, self.burst, self.tokens = ratio, burst, burst

    def record_request(self):                 # every request drips a little in
        self.tokens = min(self.burst, self.tokens + self.ratio)

    def allow_retry(self):                    # a retry needs one whole token
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


def storm(requests=1000, budget=None):
    """Sale day: every first attempt fails. How many retries does the budget allow?"""
    budget, retries = budget or RetryBudget(), 0
    for _ in range(requests):
        budget.record_request()
        retries += budget.allow_retry()
    return retries
