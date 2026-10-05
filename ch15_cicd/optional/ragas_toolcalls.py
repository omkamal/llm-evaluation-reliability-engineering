"""Chapter 15, Tool Box: Relay's tool calls scored with Ragas.

Not run by pytest or CI. Run once in a throwaway virtualenv with
ragas 0.4.3 and langchain-community 0.3.31 on 5 October 2026:
    python ch15_cicd/optional/ragas_toolcalls.py
ToolCallAccuracy compares calls with a reference and needs no model.
"""
import asyncio

from ragas.messages import AIMessage, HumanMessage, ToolCall
from ragas.metrics.collections import ToolCallAccuracy

LOOKUP = ToolCall(name="lookup_order", args={"order_id": "ORD-1042"})
RESCHEDULE = ToolCall(name="reschedule_delivery",
                      args={"order_id": "ORD-1042", "window": "Fri"})


def parcel_question(calls):
    """'Where is my parcel?' with the tool calls Relay actually made."""
    return [HumanMessage(content="Where is my parcel?"),
            AIMessage(content="Your parcel is in transit.",
                      tool_calls=calls)]


metric = ToolCallAccuracy()
for label, calls in (("current", [LOOKUP]),
                     ("friday", [LOOKUP, RESCHEDULE])):
    result = asyncio.run(metric.ascore(
        user_input=parcel_question(calls), reference_tool_calls=[LOOKUP]))
    print(f"{label}: ToolCallAccuracy {result.value}")
