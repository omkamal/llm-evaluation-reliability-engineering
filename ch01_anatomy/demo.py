"""Chapter 1 in numbers.   python3 -m ch01_anatomy.demo"""
import random

from ch01_anatomy.agent_loop import run_agent
from ch01_anatomy.call import complete, log_line
from ch01_anatomy.context import fit_to_window
from ch01_anatomy.sampling import sample


def main():
    print("== one call, metered")
    prompt = "Where is order ORD-004829? Reply in one sentence."
    c = complete(prompt, answer="It left the depot this morning and arrives tomorrow.",
                 max_tokens=40)
    print(log_line("req-001", "a-large-v1", c))

    print("== cut off by max_tokens")
    c = complete(prompt, answer="It left the depot this morning and arrives tomorrow.",
                 max_tokens=5)
    print(f"{c.finish_reason}: {c.text!r}")

    print("== sampling")
    options, logits = ["refund", "return", "replace"], [2.0, 1.6, 0.4]
    rng = random.Random(11)
    for t in (0, 1.0):
        print(f"temperature {t}:", [sample(options, logits, t, rng) for _ in range(6)])

    print("== the window overflows")
    turns = ["You are Relay, Crateway's support assistant.",
             "My address is 14 Elm Street, Apt 3.",
             "I ordered a lamp last week.",
             "It has not arrived and I need it by Friday.",
             "Can you check the status and tell me when it will be here?"]
    kept, dropped = fit_to_window(turns, window_tokens=40)
    print(f"kept {len(kept)} turns, dropped {len(dropped)}:")
    for d in dropped:
        print("  dropped:", d)

    print("== the agent loop")
    script = iter([("tool", "lookup_order", {"order_id": "ORD-004829"}),
                   ("answer", "Order ORD-004829 arrives tomorrow.")])
    answer, history = run_agent("Where is my order?", lambda h: next(script),
                                {"lookup_order": lambda order_id: "out for delivery"})
    for kind, text in history:
        print(f"  {kind}: {text}")
    print("  answer:", answer)


if __name__ == "__main__":
    main()
