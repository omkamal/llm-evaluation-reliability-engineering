"""A simulated LLM judge that fails in the ways real judges fail.

This is a stand-in for the one line where your code calls a model. It is
deterministic and seeded, so everything in the chapter runs offline. Its
flaws are knobs, and the numbers on the knobs are ILLUSTRATIVE: they are
not measurements of any real model. What the code demonstrates is the
procedure (find the flaw, apply the fix, measure that it worked), not the
size of the effect on your own judge.
"""
import json
import random
from dataclasses import dataclass

from ch05_judge.verdict import ANCHORS


@dataclass(frozen=True)
class Temperament:
    """How a model family tends to misjudge, in points on 1-5."""
    family: str
    lean: float = 1.0       # leniency: added to every score
    first: float = 0.6      # position bias: bonus for the first answer
    long: float = 0.05      # verbosity bias: per word beyond 20
    kin: float = 0.6        # self-preference: bonus for its own family
    charm: float = 1.0      # authority bias: bonus for a confident tone
    wobble: float = 0.9     # random noise, one standard deviation
    signal: float = 0.45    # how much true quality shows through, 0 to 1


@dataclass(frozen=True)
class JudgeConfig:
    """A judge is a bundle: model + prompt. Change either, it is new."""
    version: str
    model: Temperament
    anchored: bool = False        # rubric levels spelled out
    evidence_first: bool = False  # write the evidence before the score
    few_shot: bool = False        # graded examples in the prompt
    style_note: bool = False      # "do not reward length or confidence"


def effective(cfg):
    """What each prompt feature buys: the knobs after the prompt acts."""
    m = cfg.model
    lean, first, long_, wobble = m.lean, m.first, m.long, m.wobble
    signal, charm = m.signal, m.charm
    if cfg.anchored:      # it now knows what a 1, a 3 and a 5 look like
        lean, wobble, signal = lean * 0.2, wobble * 0.7, signal + 0.4
    if cfg.evidence_first:
        wobble *= 0.7
    if cfg.few_shot:
        lean, first = lean * 0.5, first * 0.5
    if cfg.style_note:
        long_, charm = long_ * 0.05, charm * 0.1
    return lean, first, long_, m.kin, wobble, min(signal, 1.0), charm


def _felt(cfg, answer, listed_first=False, salt=""):
    """The score the judge 'feels' for one answer, before rounding."""
    lean, first, long_, kin, wobble, signal, charm = effective(cfg)
    taste = random.Random(f"{cfg.model.family}|{answer.id}")   # steady
    luck = random.Random(f"{cfg.model.family}|{answer.id}|{salt}")
    noise = 0.8 * taste.gauss(0, 1) + 0.6 * luck.gauss(0, 1)
    felt = 3 + signal * (answer.quality - 3) + lean + wobble * noise
    felt += long_ * max(0, answer.words - 20)
    felt += charm if answer.eager else 0.0
    felt += first if listed_first else 0.0
    felt += kin if answer.author == cfg.model.family else 0.0
    return felt


def score_of(cfg, answer):
    """A 1-5 score for one answer on its own (pointwise)."""
    return max(1, min(5, round(_felt(cfg, answer))))


def reply(cfg, question, answer):
    """The JSON a model would send back for a pointwise request."""
    score = score_of(cfg, answer)
    return json.dumps({
        "evidence": f"Level {score}: {ANCHORS[score]}.",
        "score": score,
        "verdict": "pass" if score >= 4 else "fail",
    })


def compare(cfg, first, second, margin=0.25):
    """Pairwise: 'A' (the first-listed), 'B' (the second) or 'tie'."""
    fa = _felt(cfg, first, listed_first=True, salt="A")
    fb = _felt(cfg, second, salt="B")
    return "tie" if abs(fa - fb) < margin else ("A" if fa > fb else "B")
