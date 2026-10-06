"""The four numbers to watch for model outputs."""
from dataclasses import dataclass


@dataclass
class Day:
    first_pass: int          # valid on the first try
    repaired: int            # failed first, fixed by repair
    truncated: int           # cut off by the token limit
    terminal: int            # still invalid after repair

    @property
    def total(self):
        return self.first_pass + self.repaired + self.truncated + self.terminal

    def numbers(self):
        attempted = self.repaired + self.terminal      # repair was tried
        repair = self.repaired / attempted if attempted else 1.0
        return {
            "first-pass validity": self.first_pass / self.total,
            "repair success": repair,
            "truncation rate": self.truncated / self.total,
            "terminal failure rate": self.terminal / self.total,
        }
