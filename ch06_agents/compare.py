"""Compare two versions of Relay on the same cases, using the shared
statistics of Chapter 4 (code/ch04_numbers/stats.py)."""
from ch04_numbers.stats import paired_bootstrap, proportion_ci
from ch06_agents.evaluate import passed, run_case


def outcomes(agent, cases):
    """1 for each case Relay passes, else 0, in case order."""
    return [int(passed(c, run_case(agent, c))) for c in cases]


def slices(cases):
    """Indexes of the trigger cases and of the non-trigger cases."""
    yes = [i for i, c in enumerate(cases) if c["should_act"]]
    no = [i for i, c in enumerate(cases) if not c["should_act"]]
    return {"all": list(range(len(cases))), "trigger": yes,
            "non-trigger": no}


def paired_change(a, b, idx, seed=1):
    """Mean change in pass rate from a to b over the cases in idx, with a
    95% bootstrap interval. Paired: case i is compared with itself."""
    return paired_bootstrap([a[i] for i in idx], [b[i] for i in idx],
                            seed=seed)


def pass_rate(results):
    p, _, (lo, hi) = proportion_ci(sum(results), len(results))
    return p, lo, hi
