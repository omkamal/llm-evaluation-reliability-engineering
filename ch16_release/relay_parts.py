"""The parts of Relay's bundles, small and invented for the book."""
from datetime import date

from ch08_rag.corpus import DOCS
from ch08_rag.lifecycle import build_index

PROMPT_V14 = ("You are Relay, ParcelPath's assistant. Answer policy "
              "questions only from lookup_policy. Act only when asked.")
PROMPT_V15 = PROMPT_V14 + (" Quote numbers exactly as the policy page "
                           "states them; never state a window from memory.")

TOOLS = {
    "lookup_order": {"order_id": "str"},
    "lookup_policy": {"topic": "str"},
    "create_ticket": {"severity": "enum", "affected_services": "list",
                      "description": "str", "timestamp": "str"},
    "reschedule_delivery": {"order_id": "str", "window": "str"},
    "reset_password": {"user": "str"},
    "escalate_incident": {"id": "str", "priority": "str", "group": "str"},
    "issue_refund": {"order_id": "str", "amount_cents": "int",
                     "reason": "str"},
    "escalate_to_human": {"reason": "str", "context_packet": "dict"},
}
POLICY = {"refund_auto_cents": 5000, "approval_above": "human",
          "eu_data": "eu-eligible providers only"}
CONFIG = {"max_steps": 12, "max_tokens": 40_000, "max_usd": 0.50,
          "max_seconds": 90, "retry_budget": 0.1}


def contents(prompt, model, prompt_label):
    """The six parts, each as (label, content)."""
    index = build_index("v2", DOCS, date(2026, 9, 1))
    return {"prompt": (prompt_label, prompt), "model": (model, model),
            "tools": ("8 tools, schema v3", TOOLS),
            "index": (f"index {index.label}", index.manifest),
            "policy": ("policy v5", POLICY), "config": ("config v9", CONFIG)}
