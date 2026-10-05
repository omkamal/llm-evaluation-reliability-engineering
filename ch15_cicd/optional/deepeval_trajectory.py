"""Chapter 15, Tool Box: Relay's trajectory check as a DeepEval test.

Not run by pytest or CI. Run once in a throwaway virtualenv with
deepeval 4.2.8 on 5 October 2026 (see the chapter):
    PYTHONPATH=. pytest ch15_cicd/optional/deepeval_trajectory.py
"""
from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase, ToolCall

from ch06_agents.cases import make_case
from ch06_agents.evaluate import run_case
from ch06_agents.relays import extra_effects


class ExtraCalls(BaseMetric):
    """Deterministic: fails if Relay called a tool nobody asked for."""
    threshold = 1.0
    __name__ = "ExtraCalls"

    def measure(self, case, *args, **kwargs):
        used = [t.name for t in case.tools_called]
        wanted = [t.name for t in case.expected_tools]
        extra = [name for name in used if name not in wanted]
        self.success = not extra
        self.score = float(self.success)
        self.reason = f"extra calls: {extra}"
        return self.score

    async def a_measure(self, case, *args, **kwargs):
        return self.measure(case)

    def is_successful(self):
        return self.success


def test_where_is_my_parcel_changes_nothing():
    case = make_case("T5")                    # "Where is my parcel?"
    run = run_case(extra_effects, case)       # the Friday-style Relay
    used = [c["tool"] for c in run["after"]["tool_calls"]]
    test_case = LLMTestCase(
        input=case["message"], actual_output=run["transcript"][-1][1],
        tools_called=[ToolCall(name=t) for t in used],
        expected_tools=[ToolCall(name="lookup_order")])
    assert_test(test_case, [ExtraCalls()])
