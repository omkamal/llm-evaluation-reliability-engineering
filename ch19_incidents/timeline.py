"""One clock for an incident: machine events from a trace, human events
from the scribe's live log, merged and measured."""
import json


def at(hhmm):
    """'14:02' -> seconds since midnight, the demo clock."""
    hours, minutes = hhmm.split(":")
    return int(hours) * 3600 + int(minutes) * 60


def clock_text(seconds):
    return f"{int(seconds) // 3600:02d}:{int(seconds) % 3600 // 60:02d}"


def trace_rows(spans):
    """Rows (time, source, text) from one trace: the message that opened
    it, and every tool call that changed something (tier 1 or 2)."""
    rows = []
    for sp in sorted(spans, key=lambda s: s.start):
        a = sp.attributes
        if sp.parent_id is None:
            rows.append((sp.start, "trace", "message arrives, "
                         f"conversation {a['gen_ai.conversation.id']}"))
        elif sp.kind == "tool" and a["relay.tool.tier"] >= 1:
            args = json.loads(a["relay.tool.args"])
            # the reason code stays in the trace, to keep one line short
            shown = " ".join(f"{k}={v}" for k, v in args.items()
                             if k != "reason")
            rows.append((sp.start, "trace",
                         f"{a['gen_ai.tool.name']} {shown}"))
    return rows


class Scribe:
    """The live log: one line per thing a person did or learned.
    A note can also stamp a named mark, for the numbers below."""

    def __init__(self, clock):
        self.clock, self.rows, self.marks = clock, [], {}

    def note(self, text, mark=None):
        self.rows.append((self.clock.now(), "people", text))
        if mark:
            self.marks[mark] = self.clock.now()


def merge(*row_lists):
    """One timeline, oldest first. Ties keep the order given."""
    return sorted((r for rows in row_lists for r in rows),
                  key=lambda r: r[0])


def render(rows):
    return [f"{clock_text(t)}  {src:<7} {text}" for t, src, text in rows]


def minutes_between(marks, first, last):
    return round((marks[last] - marks[first]) / 60)


def durations(marks):
    """The three numbers a postmortem opens with, in minutes."""
    return {
        "detect": minutes_between(marks, "arrived", "declared"),
        "harm open": minutes_between(marks, "harm", "braked"),
        "first brake": minutes_between(marks, "declared", "braked"),
        "contain": minutes_between(marks, "declared", "contained"),
        "message to pin": minutes_between(marks, "arrived", "contained"),
    }
