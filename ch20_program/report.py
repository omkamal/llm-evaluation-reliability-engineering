"""An honest one-page quarterly report on the program.

Every line says whether its number was measured or assumed. A line with
no basis (none given, or any other word) is refused, so an invented
return on investment cannot slip in looking like a fact.
"""
from dataclasses import dataclass
from textwrap import fill

BASES = ("measured", "assumed")


@dataclass(frozen=True)
class Line:
    text: str
    basis: str = ""         # "measured" or "assumed"; nothing is refused


def expected_loss_avoided(reviews, error_rate, loss_usd, review_usd):
    """(cost of the reviews, the most expected loss they can prevent), in
    dollars: the upper bound holds only if every review catches the
    error (Chapter 18 measures how many do)."""
    return reviews * review_usd, reviews * error_rate * loss_usd


def render(title, sections):
    """Plain text, wrapped to 72 columns. `sections` is a list of
    (heading, [Line, ...])."""
    out = [title, "Every number is measured unless it says (assumed).", ""]
    for heading, lines in sections:
        out.append(heading)
        for line in lines:
            if line.basis not in BASES:
                raise ValueError(f"no basis for: {line.text}")
            text = line.text + (" (assumed)"
                                if line.basis == "assumed" else "")
            out.append(fill(text, 72, initial_indent="  ",
                            subsequent_indent="    "))
        out.append("")
    return out[:-1]
