"""Pager load: who was woken, how often, and by which rule.

Google's SRE book caps a 12-hour on-call shift at two incidents and the
share of a person's time on call at a quarter. We count pages, not
incidents (one problem can ring several times), which is stricter.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Page:
    when: datetime
    rule: str
    acted: bool          # did a person do anything about it?


@dataclass(frozen=True)
class Caps:
    per_shift: int = 2           # pages in one 12-hour shift
    on_call_share: float = 0.25  # of all days, per person
    precision: float = 0.5       # Chapter 13's bar for a page rule
    min_pages: int = 3           # too few to judge a rule below this


def shift_of(when):
    """Day shift 08:00 to 20:00, night 20:00 to 08:00. A night belongs
    to the date it starts on, so a page at 02:00 is last night's."""
    if 8 <= when.hour < 20:
        return when.date(), "day"
    start = when.date() if when.hour >= 20 else when.date() - timedelta(1)
    return start, "night"


def on_call(rota, first_day, day):
    """One person a week, the rota repeating."""
    return rota[((day - first_day).days // 7) % len(rota)]


def shifts_by_person(pages, rota, first_day):
    """{person: Counter of (date, kind) -> pages}."""
    out = {}
    for page in pages:
        day, kind = shift_of(page.when)
        who = on_call(rota, first_day, day)
        out.setdefault(who, Counter())[(day, kind)] += 1
    return out


def days_on_call(rota, first_day, days):
    """{person: days on call in the first `days` days}."""
    count = Counter(on_call(rota, first_day, first_day + timedelta(d))
                    for d in range(days))
    return {who: count[who] for who in dict.fromkeys(rota)}


def person_flags(pages, rota, first_day, days, caps=Caps()):
    """A person over the cap on pages in a shift, or on time on call."""
    flags = []
    mine = shifts_by_person(pages, rota, first_day)
    for who, shifts in sorted(mine.items()):
        for (day, kind), n in sorted(shifts.items()):
            if n > caps.per_shift:
                flags.append(f"{who}: {n} pages in the {kind} shift of "
                             f"{day:%d %b} (cap {caps.per_shift})")
    for who, n in days_on_call(rota, first_day, days).items():
        if n / days > caps.on_call_share:
            flags.append(f"{who}: on call {n / days:.0%} of days "
                         f"(cap {caps.on_call_share:.0%})")
    return flags


def rule_stats(pages):
    """{rule: (pages, acted on)}"""
    seen = Counter(p.rule for p in pages)
    acted = Counter(p.rule for p in pages if p.acted)
    return {rule: (n, acted[rule]) for rule, n in seen.items()}


def rule_flags(pages, caps=Caps()):
    """A rule that rings often and is rarely worth the call."""
    flags = []
    for rule, (n, acted) in sorted(rule_stats(pages).items()):
        if n >= caps.min_pages and acted / n < caps.precision:
            flags.append(f"rule '{rule}': {n}/{len(pages)} pages, "
                         f"{acted} acted on, precision {acted / n:.2f}")
    return flags


def rest_owed(pages, rota, first_day, caps=Caps()):
    """Night shifts over the cap: the person rests the next day."""
    owed = []
    for who, shifts in shifts_by_person(pages, rota, first_day).items():
        for (day, kind), n in shifts.items():
            if kind == "night" and n > caps.per_shift:
                owed.append((who, day + timedelta(1)))
    return sorted(owed)
