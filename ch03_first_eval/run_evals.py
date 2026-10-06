"""Score a version of Relay against Relay-30.   python3 -m ch03_first_eval.run_evals [v1|v2]"""
import re
import sys
import textwrap

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


def run(version, cases=CASES, ask=ask, answers=None):
    """One trial of every case. Returns [(case_id, passed, reason), ...].

    `ask` is the seam: pass your own model call, or a copy of the stand-in.
    Pass a dict as `answers` to keep every answer by case id, so that a
    failure can be read and not only counted.
    """
    out = []
    for case in cases:
        answer = ask(case["question"], version)
        if answers is not None:          # keep the transcript to read
            answers[case["id"]] = answer
        passed, why = grade(case, answer)
        out.append((case["id"], passed, why))
    return out


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    answers = {}
    results = run(version, answers=answers)
    passed = sum(p for _, p, _ in results)
    print(f"Relay {version}: {passed}/{len(results)} passed ({passed / len(results):.0%})")
    for cid, ok, why in results:
        if not ok:                       # print what Relay said, to read it
            print(f"  FAIL {cid}: {why}")
            print(textwrap.fill(f'"{answers[cid]}"', 72, initial_indent="    ",
                                subsequent_indent="     "))
