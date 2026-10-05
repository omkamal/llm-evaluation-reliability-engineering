"""Memory is input too. A note an agent saved last week was written by
somebody, and it is read back as data: it can inform an answer, never
grant authority. Three rules, all enforced by code."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Note:
    about: str      # which customer the note concerns
    text: str
    source: str     # who wrote it: "summarizer", "agent", "staff"


class MemoryRefused(Exception):
    pass


class Memory:
    def __init__(self):
        self.notes = []

    def write(self, session, note):
        """Rule 1: a session may only write about its own customer.
        Rule 2: every note carries its source."""
        if note.about != session.customer_id:
            raise MemoryRefused(f"{session.customer_id} cannot write "
                                f"about {note.about}")
        if not note.source:
            raise MemoryRefused("a note without a source")
        self.notes.append(note)

    def read(self, customer_id):
        """Rule 3 lives in the guard: nothing returned here is ever
        consulted for who owns what."""
        return [n for n in self.notes if n.about == customer_id]
