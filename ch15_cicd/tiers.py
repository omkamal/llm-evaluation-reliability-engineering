"""Three CI tiers and the path filter that decides whether to run them."""
import random
import re
from dataclasses import dataclass


SAFETY_TRIALS = 20     # --safety: each never-fail case runs this often


@dataclass(frozen=True)
class Tier:
    name: str
    sample: int = None     # cases per run; None means the whole set
    trials: int = 1        # trials per case
    safety: bool = False   # run the never-fail cases SAFETY_TRIALS times

    @property
    def safety_trials(self):
        return SAFETY_TRIALS if self.safety else 0


TIERS = {
    "smoke": Tier("smoke", sample=50),                      # every PR
    "full": Tier("full", trials=3),                         # nightly
    "release": Tier("release", trials=5, safety=True),      # tags
}


def pick_sample(case_ids, never_fail, k, seed):
    """k cases for a smoke run: every never-fail case, then a random
    rest. A different seed on each run rotates through the whole set."""
    ids = sorted(case_ids)
    if k is None or k >= len(ids):
        return ids
    must = [i for i in ids if i in never_fail]
    rest = [i for i in ids if i not in never_fail]
    chosen = random.Random(seed).sample(rest, k - len(must))
    return sorted(must + chosen)


# The paths where a change can alter Relay's behavior, or the verdict:
# the gate's own code, its packages and its workflow count too, since a
# pull request runs its own copy of them. Everything else (a README, a
# stylesheet) does not need an eval.
TRIGGER_PATHS = (
    "ch15_cicd/relay/prompts/**",
    "ch15_cicd/relay/schemas/**",
    "ch15_cicd/relay/config/**",
    "ch15_cicd/relay/evals/**",
    "ch15_cicd/*.py",
    "requirements*.txt",
    ".github/workflows/evals.yml",
)


def _regex(pattern):
    """GitHub's glob: `**` crosses folders, `*` stays inside one."""
    parts = re.split(r"(\*\*|\*)", pattern)
    body = "".join(".*" if p == "**" else "[^/]*" if p == "*"
                   else re.escape(p) for p in parts)
    return re.compile(body + r"\Z")


def needs_evals(changed_paths, patterns=TRIGGER_PATHS):
    """True when any changed file can change what Relay does."""
    rules = [_regex(p) for p in patterns]
    return any(r.match(path) for path in changed_paths for r in rules)
