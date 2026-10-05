"""Score a version of Relay against Relay-30.   python3 -m ch03_first_eval.run_evals [v1|v2]"""
import re
import sys

from common.relay_fake import ask
from ch03_first_eval.cases import CASES


def grade(case, answer):
    """Return (passed, reason). Pure code: fast, free, and the same verdict every time."""
    for pattern in case["must_contain"]:
        if not re.search(pattern, answer, re.I):
            return False, f"missing /{pattern}/"
    for pattern in case["must_not_contain"]:
        if re.search(pattern, answer, re.I):
            return False, f"volunteered /{pattern}/"
    return True, "ok"


def run(version, cases=CASES):
    """One trial of every case. Returns [(case_id, passed, reason), ...]."""
    out = []
    for case in cases:
        passed, why = grade(case, ask(case["question"], version))
        out.append((case["id"], passed, why))
    return out


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    results = run(version)
    passed = sum(p for _, p, _ in results)
    print(f"Relay {version}: {passed}/{len(results)} passed ({passed / len(results):.0%})")
    for cid, ok, why in results:
        if not ok:
            print(f"  FAIL {cid}: {why}")
