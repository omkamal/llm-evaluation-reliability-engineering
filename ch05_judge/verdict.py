"""The judge's prompt and its structured verdict (Chapter 5)."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ch02_trust_outputs.gateway import Gateway

# The rubric, anchored: the judge knows what a 1, a 3 and a 5 look like.
ANCHORS = {
    1: "invents a policy that does not exist",
    2: "gets part of the policy wrong",
    3: "vague policy, no usable figure",
    4: "correct policy, not cited",
    5: "cites the correct policy",
}
RUBRIC = """\
Score the answer from 1 to 5 against the ParcelPath policy sheet.
5  Cites the correct policy.
4  Correct policy, not cited.
3  Vague policy: no usable figure.
2  Gets part of the policy wrong.
1  Invents a policy that does not exist.
Pass means 4 or 5. Do not reward length, warmth or confidence."""


class Verdict(BaseModel, extra="forbid"):
    # Field order is generation order: evidence first, then the decision.
    evidence: str = Field(min_length=1,
                          description="Quote the answer, name its level.")
    score: Literal[1, 2, 3, 4, 5]
    verdict: Literal["pass", "fail"]

    @model_validator(mode="after")
    def decision_matches_score(self):
        if (self.score >= 4) != (self.verdict == "pass"):
            raise ValueError("pass means a score of 4 or 5")
        return self


def build_prompt(question, answer, rubric=RUBRIC):
    """Task, rubric, evidence first, then the verdict as JSON."""
    return "\n\n".join([
        "TASK\nGrade one reply from Relay, ParcelPath's assistant.",
        f"QUESTION\n{question}",
        f"ANSWER\n{answer}",
        f"RUBRIC\n{rubric}",
        "EVIDENCE FIRST\nQuote the part of the answer you are scoring,\n"
        "say which level it matches, and only then give the score.",
        'REPLY (JSON only)\n{"evidence": str, "score": 1-5, '
        '"verdict": "pass" | "fail"}',
    ])


def grade(gateway, question, answer, ask_model, version="v2"):
    """Prompt, call, validate. None means the reply was quarantined."""
    prompt = build_prompt(question, answer.text)
    raw = ask_model(prompt)       # the one line a real system swaps out
    return gateway.check(raw, prompt_version=version,
                         model_version="judge")


def verdict_gateway():
    """Chapter 2's gateway, pointed at the judge's schema."""
    return Gateway(schema=Verdict)
