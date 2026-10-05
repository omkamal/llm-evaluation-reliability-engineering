"""Chapter 15, Tool Box: Relay-30 as an Inspect task.

Not run by pytest or CI. Run once in a throwaway virtualenv with
inspect-ai 0.3.276 on 5 October 2026 (see the chapter):
    PYTHONPATH=. inspect eval ch15_cicd/optional/inspect_relay.py \
        --model mockllm/model -T version=v2
The scripted Relay answers; the mock model is never called.
"""
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import (CORRECT, INCORRECT, Score, accuracy,
                               scorer, stderr)
from inspect_ai.solver import Generate, TaskState, solver

from ch03_first_eval.cases import CASES
from ch03_first_eval.run_evals import grade
from common.relay_fake import ask

BY_ID = {case["id"]: case for case in CASES}


@solver
def relay(version):
    async def solve(state: TaskState, generate: Generate):
        state.output.completion = ask(state.input_text, version)
        return state
    return solve


@scorer(metrics=[accuracy(), stderr()])
def relay_grader():
    async def score(state: TaskState, target):
        passed, why = grade(BY_ID[state.sample_id],
                            state.output.completion)
        return Score(value=CORRECT if passed else INCORRECT,
                     explanation=why)
    return score


@task
def relay30(version="v1"):
    samples = [Sample(id=c["id"], input=c["question"]) for c in CASES]
    return Task(dataset=samples, solver=relay(version),
                scorer=relay_grader(), epochs=3)
