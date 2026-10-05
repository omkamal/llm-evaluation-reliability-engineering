"""When does a person look? The expected-loss rule and five triggers."""
from dataclasses import dataclass, field

from ch10_providers.tiers import IRREVERSIBLE

REVIEW_COST_CENTS = 150       # what one human review costs ($1.50)


def expected_loss_cents(p_error, amount_cents):
    return p_error * amount_cents


def needs_review(p_error, amount_cents,
                 review_cost_cents=REVIEW_COST_CENTS):
    """A person looks when being wrong costs more than looking."""
    return expected_loss_cents(p_error, amount_cents) > review_cost_cents


def break_even_cents(p_error, review_cost_cents=REVIEW_COST_CENTS):
    """The amount above which a review pays for itself."""
    return review_cost_cents / p_error


@dataclass
class Case:
    case_id: str
    task: str
    customer: str            # from the session, never from the model
    trace: str
    tool: str
    args: dict
    summary: str
    p_error: float = 0.02    # measured on this kind of request
    confidence: float = 1.0  # do the Planner's own checks agree?
    policy_unclear: bool = False
    failures: int = 0
    user_asked: bool = False
    evidence: list = field(default_factory=list)


def triggers(case, min_confidence=0.7, max_failures=2):
    """The names of the five reasons to hand off to a human."""
    found = []
    if case.user_asked:
        found.append("user_request")
    if case.failures >= max_failures:
        found.append("repeated_failure")
    if case.policy_unclear:
        found.append("policy_ambiguity")
    if case.confidence < min_confidence:
        found.append("low_confidence")
    if needs_review(case.p_error, case.args.get("amount_cents", 0)):
        found.append("high_value")
    return found


def review_mode(tool):
    """Irreversible actions wait for the person; the rest go now."""
    return "block" if tool in IRREVERSIBLE else "async"
