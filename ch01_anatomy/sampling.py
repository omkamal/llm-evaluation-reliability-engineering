"""Why the same prompt gives different answers: the model samples from probabilities."""
import math
import random


def sample(options, logits, temperature, rng):
    """Pick one option. Temperature 0 always takes the most likely one."""
    if temperature == 0:
        return options[max(range(len(options)), key=lambda i: logits[i])]
    weights = [math.exp(x / temperature) for x in logits]
    return rng.choices(options, weights=weights)[0]


if __name__ == "__main__":
    options = ["refund", "return", "replace"]
    logits = [2.0, 1.6, 0.4]
    rng = random.Random(2)
    for t in (0, 1.0):
        print(f"temperature {t}:", [sample(options, logits, t, rng) for _ in range(8)])
