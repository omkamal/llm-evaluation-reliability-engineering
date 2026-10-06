"""Relay answers with a known quality, for testing judges.

Every answer carries the quality the support lead would give it (1 to 5).
A real judge never sees that number; the simulated judge in simjudge.py
sees a noisy, biased version of it. The text is only there for its length.
"""
import random
from dataclasses import dataclass

# What each level of the rubric looks like for one policy topic.
# 5 cites the policy, 3 is vague, 1 invents it (the Friday tweak).
LEVELS = {
    "returns": {
        5: "Returns are accepted within 14 days of delivery, per our "
           "returns policy.",
        4: "You can return unused items within 14 days of delivery.",
        3: "Returns are possible for a limited time, so please check "
           "the policy page.",
        2: "You can usually return items within about three weeks.",
        1: "You have 30 days to return anything, and I can reschedule "
           "it for you now.",
    },
    "refund": {
        5: "Refunds arrive 5 business days after we receive the item, "
           "per our refund policy.",
        4: "Your refund is issued 5 business days after we get the item.",
        3: "Refunds take a little while, so please be patient.",
        2: "Refunds usually arrive within two weeks.",
        1: "Refunds are instant, and I have already sent yours.",
    },
    "windows": {
        5: "Deliveries run in two-hour windows between 8:00 and 20:00, "
           "Monday to Saturday, per our delivery policy.",
        4: "Delivery windows are two hours long, 8:00 to 20:00.",
        3: "Deliveries happen during the day, on most days.",
        2: "Deliveries run all week, between 8:00 and 22:00.",
        1: "Deliveries arrive at midnight, and I have moved yours.",
    },
}
EAGER = "I can take care of that for you right now."
# Answers a code check or a hand-off flagged: rich in fails (60%), with
# the three kinds of fail in the same proportions as everyday traffic.
FLAGGED = (10, 20, 30, 20, 20)
FLUFF = ["Thanks for reaching out to Crateway.",
         "I hope that helps, and I am glad to look at anything else.",
         "It is no trouble at all, and we value your patience."]


@dataclass(frozen=True)
class Answer:
    id: str
    question: str
    text: str
    quality: int            # the support lead's score, 1 to 5
    author: str = "a"       # model family that wrote it (Relay runs on a)
    eager: bool = False     # sounds proactive and confident

    @property
    def words(self):
        return len(self.text.split())


def expert_label(answer):
    """The support lead's decision: 4 and 5 pass, 1 to 3 fail."""
    return "pass" if answer.quality >= 4 else "fail"


def make_answers(n, seed, weights=(5, 10, 15, 35, 35), prefix="r",
                 author="a"):
    """n seeded answers; `weights` are the shares of quality 1 to 5.

    About a third get a polite padding sentence or two, so length varies
    independently of quality: a judge that likes length is then easy to
    catch.
    """
    rng = random.Random(seed)
    out = []
    for i in range(n):
        topic = rng.choice(sorted(LEVELS))
        quality = rng.choices([1, 2, 3, 4, 5], weights)[0]
        text = LEVELS[topic][quality]
        if rng.random() < 0.35:
            text += " " + " ".join(rng.sample(FLUFF, rng.randint(1, 3)))
        out.append(Answer(f"{prefix}-{i:03d}", f"{topic}?", text, quality,
                          author))
    return out


def pad(answer):
    """The "repetitive list" attack: same facts, restated."""
    again = "To say it another way: " + answer.text
    return Answer(answer.id + "+", answer.question,
                  answer.text + " " + again, answer.quality,
                  answer.author)


def friday_tweak(answers, seed, share=0.3):
    """The same questions after the Friday tweak: some answers now invent
    a policy, and every answer sounds more eager."""
    rng = random.Random(seed)
    out = []
    for a in answers:
        text, quality = a.text, a.quality
        if rng.random() < share:
            text, quality = LEVELS[a.question[:-1]][1], 1
        out.append(Answer(a.id, a.question, text + " " + EAGER, quality,
                          a.author, eager=True))
    return out


def twin(answer, author=None):
    """A second answer of equal quality, for the position test.

    A real judge spots an exact copy and calls a tie, so test it on two
    different answers of equal quality (two samples of one prompt). The
    simulated judge cannot read, and gives the twin its own noise, so
    here the same words stand in for such a pair.
    """
    return Answer(answer.id + "~", answer.question, answer.text,
                  answer.quality, author or answer.author)
