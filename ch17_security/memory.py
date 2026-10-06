"""Memory is input too. A note an agent saved last week was written by
somebody, and it is read back as data: it can inform an answer, never
grant authority. Three rules, all enforced by code."""
import json
from dataclasses import dataclass


def quoted(text, origin):
    """Text someone outside wrote, as every model and person sees it:
    labelled with its origin and quoted. The quoting escapes the text,
    so a note cannot close the quote and forge a label of its own."""
    return f"[{origin} wrote] {json.dumps(text, ensure_ascii=False)}"


@dataclass(frozen=True)
class Note:
    about: str      # which customer the note concerns
    text: str
    source: str     # who wrote it down: "summarizer", "agent", "staff"
    # who first said it; unknown counts as the customer, never as staff
    origin: str = "customer"

    def label(self):
        return f"[from {self.origin}, via {self.source}]"

    def shown(self):
        """How the note reaches a model or the staff panel: quoted."""
        return quoted(self.text, self.origin)


class MemoryRefused(Exception):
    pass


class Memory:
    def __init__(self):
        self.notes = []

    def write(self, session, note):
        """Rule 1: a session may only write about its own customer.
        Rule 2: every note carries its source and its origin."""
        if note.about != session.customer_id:
            raise MemoryRefused(f"{session.customer_id} cannot write "
                                f"about {note.about}")
        if not note.source or not note.origin:
            raise MemoryRefused("a note without a source")
        self.notes.append(note)

    def read(self, customer_id):
        """Rule 3 lives in the guard: nothing returned here is ever
        consulted for who owns what."""
        return [n for n in self.notes if n.about == customer_id]
