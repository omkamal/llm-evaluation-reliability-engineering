"""The contamination guard (Chapter 7) as a CI step.

Runs whenever the prompt, the judge's examples or the eval set change.
Exit code 1 if any test case appears inside what Relay or its judge sees.
"""
import sys

from ch07_datasets.contamination import find_leaks
from ch15_cicd import repo, suite


def check(prompt_text, judge_examples=(), cases=None, n=4):
    """(case id, where it leaked, share of its n-grams) for each leak."""
    cases = cases or suite.case_meta()
    _, body = repo.read_prompt(prompt_text)
    refs = {"prompt": body}
    refs.update({f"judge_example_{i}": text
                 for i, text in enumerate(judge_examples, 1)})
    return find_leaks(cases, refs, n=n)


def judge_examples(root=repo.ROOT):
    """The worked examples the judge sees, split on blank lines."""
    path = root / "evals" / "judge_examples.txt"
    return path.read_text().strip().split("\n\n") if path.exists() else []


def main(root=repo.ROOT):
    leaks = check((root / "prompts/system.md").read_text(),
                  judge_examples(root))
    for case_id, where, share in leaks:
        print(f"LEAK {case_id} in {where}: {share:.0%} of its 4-grams")
    print(f"contamination guard: {len(leaks)} leaks")
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
