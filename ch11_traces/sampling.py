"""Keep every interesting trace: head sampling versus tail sampling.

The traffic is simulated (seeded) and its rates are illustrative."""
import random

from ch11_traces.tracer import IdGenerator

SLOW_SECONDS = 8.0          # Relay's p95 task target (Chapter 12)


def head_keep(trace_id, rate):
    """Decide at the first span, blind: a fixed slice of trace ids."""
    return int(trace_id[16:], 16) / 16 ** 16 < rate


def tail_keep(trace, rate=0.05):
    """Decide after the run ends: errors and slow runs always stay."""
    if trace["error"] or trace["seconds"] > SLOW_SECONDS:
        return True
    return head_keep(trace["id"], rate)      # plus a small random slice


def simulate_traffic(n=1_000, seed=3):
    """Illustrative: 3% of runs fail; durations are right-skewed."""
    rng, ids = random.Random(seed), IdGenerator(seed)
    return [{"id": ids.trace_id(), "error": rng.random() < 0.03,
             "seconds": rng.lognormvariate(1.3, 0.45)} for _ in range(n)]


def compare(traces, head_rate=0.10):
    """(kept traces, kept errors, kept slow) for each policy."""
    def tally(keep):
        kept = [t for t in traces if keep(t)]
        return (len(kept), sum(t["error"] for t in kept),
                sum(t["seconds"] > SLOW_SECONDS for t in kept))
    return (tally(lambda t: head_keep(t["id"], head_rate)),
            tally(tail_keep))
