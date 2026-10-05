"""Simulated live traffic for Relay. Illustrative, seeded and offline.

A `Chat` is what a customer brings; a `Version` is one release of Relay.
The same version always gives the same outcome for the same chat, so
two versions can be compared on exactly the same traffic.
"""
import random
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Chat:
    id: int
    wants_action: bool    # the customer asked for a reschedule (about 18%)
    policy_q: bool        # a policy question (35%)
    audited: bool         # in the 25% sample a state check grades


def make_chat(i, rng):
    return Chat(i, rng.random() < 0.18, rng.random() < 0.35,
                rng.random() < 0.25)


def make_chats(n, seed=16, first=0):
    rng = random.Random(seed)
    return [make_chat(first + i, rng) for i in range(n)]


@dataclass(frozen=True)
class Outcome:
    failed: bool            # an error the customer saw
    slow: bool              # first token later than 2 s
    invalid: bool           # first-pass output failed validation
    acted: bool             # reschedule_delivery ran
    unasked: bool           # it ran and nobody asked (ground truth)
    false_act: object       # unasked, but known only if audited
    wrong_policy: object    # wrong answer, known only if audited


@dataclass(frozen=True)
class Version:
    name: str
    p_fail: float = 0.003
    p_slow: float = 0.03
    p_invalid: float = 0.015
    false_act: float = 0.0       # acts when nobody asked
    wrong_policy: float = 0.01   # wrong answer to a policy question

    def serve(self, chat):
        rng = random.Random(f"{self.name}:{chat.id}")   # same chat, same draw
        unasked = not chat.wants_action and rng.random() < self.false_act
        acted = chat.wants_action or unasked
        wrong = chat.policy_q and rng.random() < self.wrong_policy
        return Outcome(
            failed=rng.random() < self.p_fail,
            slow=rng.random() < self.p_slow,
            invalid=rng.random() < self.p_invalid,
            acted=acted, unasked=unasked,
            false_act=unasked if chat.audited else None,
            wrong_policy=wrong if chat.audited and chat.policy_q else None)


CONTROL = Version("a-large-v1, prompt v14")
FRIDAY = replace(CONTROL, name="Friday tweak", false_act=0.23)
V2_UNTUNED = replace(CONTROL, name="a-large-v2, prompt v14", p_slow=0.015,
                     p_invalid=0.009, wrong_policy=0.12)
V2_TUNED = replace(V2_UNTUNED, name="a-large-v2, prompt v15",
                   wrong_policy=0.01)


def counts(outcomes, flag):
    """(bad, graded): chats where `flag` is True, over those that know."""
    seen = [getattr(o, flag) for o in outcomes
            if getattr(o, flag) is not None]
    return sum(seen), len(seen)


def rate(outcomes, flag):
    bad, n = counts(outcomes, flag)
    return (bad / n if n else 0.0), n
