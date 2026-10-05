"""Relay's golden set, version 3, built from the four sources."""
from ch07_datasets.card import make_card
from ch07_datasets.relay_cases import (edge_cases, monday_cases,
                                       simulated_customers, ticket_cases,
                                       traffic_log)
from ch07_datasets.sampling import stratified_sample

GAPS = ("German: 1 case; no French or Spanish",
        "no phone or voice conversations",
        "synthetic cases: 8 of 64, 3 checked by hand")


def golden_v3():
    sampled = stratified_sample(traffic_log(), 36)
    return (sampled + monday_cases() + edge_cases() + ticket_cases()
            + simulated_customers())


def golden_card(cases):
    return make_card("Relay golden set", 3, cases, created="2026-09-14",
                     owner="Marcus (support operations)", guideline=2,
                     known_gaps=GAPS)
