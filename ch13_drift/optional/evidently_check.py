"""The same drift checks with Evidently, on the chapter's EU email data.

NOT run by pytest or CI. Tested with evidently 0.7.23, Python 3.12.3,
on 5 October 2026, in a throwaway virtualenv:

    python3 -m venv /tmp/evidently-venv
    /tmp/evidently-venv/bin/pip install evidently
    cd code && /tmp/evidently-venv/bin/python \
        -m ch13_drift.optional.evidently_check
"""
import random

import pandas as pd
from evidently import Report
from evidently.metrics import ValueDrift

from ch13_drift.relay_sim import SEGMENTS, input_chars, tool_calls
from ch13_drift.shift import psi, shares

TOOLS = ["lookup_order", "lookup_policy", "reschedule_delivery",
         "issue_refund", "escalate_to_human"]


def main():
    base, now = tool_calls(SEGMENTS[-1])              # EU email
    rng = random.Random(8)
    before = pd.DataFrame({"tool": base,
                           "chars": input_chars(420, len(base), rng)})
    after = pd.DataFrame({"tool": now,
                          "chars": input_chars(560, len(now), rng)})
    report = Report([
        ValueDrift(column="tool", method="psi"),
        ValueDrift(column="tool", method="chisquare"),
        ValueDrift(column="chars", method="ks"),
    ])
    result = report.run(after, before).dict()      # current, reference
    for metric in result["metrics"]:
        cfg = metric["config"]
        print(f"{cfg['column']:>5} {cfg['method']:<9} "
              f"{metric['value']:.4f}")
    ours = psi(shares(base, TOOLS), shares(now, TOOLS))
    print(f"our PSI on the same calls: {ours:.4f}")


if __name__ == "__main__":
    main()
