"""What an eval run costs, a budget per run, and a cache of answers.

Prices are ILLUSTRATIVE (dollars per million tokens, input and output).
a-small is cheaper than a-large on both, as it should be.
"""
import hashlib

PRICES = {"a-large": (3.00, 15.00), "a-small": (0.30, 1.50)}
TRIAL = {"calls": 3, "tokens_in": 1500, "tokens_out": 150}  # per trial
JUDGE = {"calls": 1, "tokens_in": 1200, "tokens_out": 100}  # per answer
BUDGETS = {"smoke": 2.00, "full": 10.00, "release": 25.00}  # per run


def trial_cost(model, trial=TRIAL):
    price_in, price_out = PRICES[model]
    per_call = (trial["tokens_in"] * price_in
                + trial["tokens_out"] * price_out) / 1e6
    return trial["calls"] * per_call


def run_cost(model, n_trials, each=TRIAL):
    return n_trials * trial_cost(model, each)


def within_budget(tier_name, cost):
    """Check a run's planned cost before its first call: a run over its
    budget should refuse to start."""
    return cost <= BUDGETS[tier_name]


class ResultCache:
    """Never pay twice for an answer you already have.

    The key holds everything that can change the answer. Leave the trial
    number out and five trials become one answer five times, and the
    noise you wanted to measure disappears."""

    def __init__(self):
        self.store, self.hits, self.misses = {}, 0, 0

    @staticmethod
    def key(*parts):
        text = "|".join(str(part) for part in parts)
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def get(self, key, run):
        if key in self.store:
            self.hits += 1
        else:
            self.misses += 1
            self.store[key] = run()
        return self.store[key]


# The files whose text shapes an answer: the prompt, the settings (model,
# temperature, index, judge), the tool schemas and the judge's examples.
SHAPES = ("prompts/system.md", "config/", "schemas/",
          "evals/judge_examples.txt")


def answer_key(files, case, trial):
    """The cache key of one trial. It hashes texts, not version labels,
    so an edit that forgot its version bump still misses the cache."""
    texts = [files[p] for p in sorted(files) if p.startswith(SHAPES)]
    return ResultCache.key(*texts, case["id"], case["text"], trial)
