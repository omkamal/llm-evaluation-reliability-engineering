"""A first-pass redactor. It removes patterns; it does not find people."""
import re
from collections import Counter

PATTERNS = [   # order matters: a card number must not be read as a phone
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("ORDER", re.compile(r"\bORD-\d{6}\b")),
    ("CARD", re.compile(r"\b\d(?:[ -]?\d){12,18}\b")),
    ("PHONE", re.compile(r"\+?\d[\d ()-]{7,}\d")),
]


def luhn_ok(number):
    """Card numbers carry a check digit; most long numbers do not."""
    digits = [int(d) for d in re.sub(r"\D", "", number)][::-1]
    total = sum(d if i % 2 == 0 else sum(divmod(2 * d, 10))
                for i, d in enumerate(digits))
    return total % 10 == 0


CHECKS = {"CARD": luhn_ok,
          "PHONE": lambda raw: sum(c.isdigit() for c in raw) >= 9}


def redact(text):
    """Return (clean text, counts). Same value, same placeholder."""
    seen, counts = {}, Counter()

    def swap(kind):
        def sub(match):
            raw = match.group(0)
            if not CHECKS.get(kind, lambda raw: True)(raw):
                return raw      # looked like one, failed its check
            if (kind, raw) not in seen:
                n = sum(k == kind for k, _ in seen) + 1
                seen[(kind, raw)] = f"<{kind}_{n}>"
            counts[kind] += 1
            return seen[(kind, raw)]
        return sub

    for kind, pattern in PATTERNS:
        text = pattern.sub(swap(kind), text)
    return text, dict(counts)
