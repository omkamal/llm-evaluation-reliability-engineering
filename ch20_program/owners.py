"""Who answers for each thing the book built.

RACI: the Responsible person does the work, the Accountable person
answers for the result, Consulted people are asked first and Informed
people are told after. The one rule that makes the sheet worth having:
every item has exactly one Accountable name, and that person is here.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Person:
    name: str
    left: str = ""          # ISO date they left the company, or ""
    away: bool = False      # on holiday today
    deputy: str = ""        # decides for them while they are away


@dataclass(frozen=True)
class Item:
    name: str
    responsible: tuple
    accountable: tuple      # a tuple on purpose: the check counts it
    consulted: tuple = ()
    informed: tuple = ()


def check(items, roster):
    """What makes a sheet a wish. An empty list means it is sound."""
    people = {p.name: p for p in roster}
    out = []
    for item in items:
        who = item.accountable
        if len(who) != 1:
            names = ", ".join(who) or "nobody"
            out.append(f"{item.name}: accountable is {names} "
                       "(need exactly one)")
        for name in dict.fromkeys(item.accountable + item.responsible):
            person = people.get(name)
            if person is None:
                out.append(f"{item.name}: {name} is not on the roster")
            elif person.left:
                out.append(f"{item.name}: {name} left on {person.left}")
        for name in item.accountable:
            person = people.get(name)
            if person and person.away and not person.deputy:
                out.append(f"{item.name}: {name} is away, no deputy")
    return out


def single_hands(items, roster, count_away=True):
    """Items that fewer than two people still here can do: the hero list.
    Someone who left never counts; someone on holiday counts unless
    count_away is False (the test of a holiday)."""
    here = {p.name for p in roster
            if not p.left and (count_away or not p.away)}
    return [i.name for i in items
            if len([n for n in i.responsible if n in here]) < 2]


def accountable_load(items):
    """How many items each person answers for."""
    load = {}
    for item in items:
        for name in item.accountable:
            load[name] = load.get(name, 0) + 1
    return load


def rows(items):
    """The sheet as table rows: name, R, A, C, I."""
    return [(i.name, *(", ".join(group) or "-" for group in
                       (i.responsible, i.accountable, i.consulted,
                        i.informed))) for i in items]
