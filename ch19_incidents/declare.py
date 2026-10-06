"""When to declare, how bad it is, who does what.

The severity is about what the agent DID or COULD do, not whether it
is up. The targets are Relay's own, illustrative: set yours."""
from dataclasses import dataclass

# severity -> (minutes to name the roles, minutes between updates)
TARGETS = {1: (5, 30), 2: (15, 60), 3: (None, None)}


def declare_reasons(*, irreversible_action=False, customers_see=False,
                    other_team_needed=False, minutes_unsolved=0):
    """Any one reason is enough. An empty list means: keep watching."""
    why = []
    if irreversible_action:
        why.append("an action that cannot be undone")
    if customers_see:
        why.append("customers can see it")
    if other_team_needed:
        why.append("a second team is needed")
    if minutes_unsolved >= 60:
        why.append("an hour of digging has not solved it")
    return why


def response(sev):
    """The promise a severity makes, in words."""
    roles, gap = TARGETS[sev]
    if roles is None:
        return "a ticket for the next working day"
    return f"roles in {roles} min, update every {gap} min"


def severity(*, irreversible=False, data_exposed=False, broad=False,
             customers_notice=False):
    """1: harm that cannot be taken back. 2: broad decay people notice.
    3: anything contained to one segment."""
    if irreversible or data_exposed:
        return 1
    if broad and customers_notice:
        return 2
    return 3


@dataclass
class Incident:
    id: str
    sev: int
    declared: str           # clock text, "14:40"
    commander: str          # holds the picture, assigns the work
    ops: str                # the only person changing the system
    comms: str              # writes every update
    scribe: str             # keeps the live log

    def problems(self):
        out = []
        if self.commander == self.ops:
            out.append("commander is also changing the system")
        if self.comms == self.ops:
            out.append("the person changing the system writes updates")
        return out
