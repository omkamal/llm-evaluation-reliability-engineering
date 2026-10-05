"""RAG drift: the questions move away from the documents.

Chapter 8 owns index freshness: whether the index matches its sources.
This is the other half: the index can be perfectly fresh while customers
ask about things no page covers. Uses Chapter 8's index and its
`lookup_policy` tool.
"""
import random
from datetime import date

from ch08_rag.corpus import DOCS
from ch08_rag.lifecycle import build_index
from ch08_rag.queries import QUERIES
from ch08_rag.tool import lookup_policy
from ch13_drift.bands import first_alert, rate_band
from ch13_drift.shift import psi, shares

# New questions after an invented customs rule: no page covers them.
CUSTOMS = [
    "Do I owe import duty or VAT on my order?",
    "Why is my package held by customs?",
    "Which customs forms do I need?",
    "Is there a tariff on goods shipped to Germany?",
    "How long does customs clearance take?",
    "Who pays the import tax?",
    "Can you fill in the customs declaration for me?",
    "My parcel is stuck at the border, what now?",
]
PAGES = [d.id for d in DOCS] + ["none"]
RAMP = [0, 0, 0, 0, 0.05, 0.10, 0.20, 0.30]   # share of customs questions


def make_index():
    """The index Chapter 8 built; its freshness alarm stays quiet."""
    return build_index("v2", DOCS, date(2026, 9, 25))


def weekly_queries(customs_share, size, rng):
    """One week of questions: the usual mix plus some customs ones."""
    usual = [q.text for q in QUERIES]
    return [rng.choice(CUSTOMS) if rng.random() < customs_share
            else rng.choice(usual) for _ in range(size)]


def pages_read(index, queries):
    """Which page each question's best chunk came from, or 'none'."""
    best = []
    for text in queries:
        chunks = lookup_policy(index, text)["chunks"]
        best.append(chunks[0]["id"].split("#")[0] if chunks else "none")
    return best


def drift_table(index, ramp=RAMP, size=400, seed=32):
    """Per week: zero-result rate against its band, pages-read PSI."""
    rng = random.Random(seed)
    weeks = [pages_read(index, weekly_queries(c, size, rng))
             for c in ramp]
    base = [page for week in weeks[:4] for page in week]
    p0 = sum(page == "none" for page in base) / len(base)
    lo, hi = rate_band(p0, size)
    rows = []
    for number, (share, week) in enumerate(zip(ramp, weeks), 1):
        zero = week.count("none") / size
        score = psi(shares(base, PAGES), shares(week, PAGES))
        rows.append((number, share, zero, zero > hi, score))
    alert = first_alert([row[3] for row in rows], 2)
    return rows, (lo, hi), None if alert is None else alert + 1
