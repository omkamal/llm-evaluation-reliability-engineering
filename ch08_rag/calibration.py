"""Calibrating the groundedness check against a person's labels.

Each item is (document id, an answer, the human verdict on whether the
document supports the answer). The labels were written by the author,
reading the document, before the check was run.
"""
from ch05_judge.agreement import cohen_kappa, confusion, tpr_tnr
from ch08_rag.corpus import DOCS
from ch08_rag.grounding import groundedness

LABELED = [
    ("returns", "Returns are accepted for unused items within 14 days of "
     "delivery.", "pass"),
    ("returns", "You can return an unused item within 14 days of "
     "delivery.", "pass"),
    ("returns", "Unused goods can come back to us for up to fourteen "
     "days after they arrive.", "pass"),
    ("returns", "Returns are accepted within 30 days of delivery.",
     "fail"),
    ("returns", "Used items can be returned within 14 days.", "fail"),
    ("refund-timing", "We issue the refund 5 business days after the "
     "returned item is received.", "pass"),
    ("refund-timing", "Refunds go back to the payment method you used "
     "for the order.", "pass"),
    ("refund-timing", "Refunds are issued within 24 hours.", "fail"),
    ("damaged", "Report the damage within 7 days and include a photo.",
     "pass"),
    ("damaged", "We will send a free replacement or a refund.", "pass"),
    ("damaged", "You have a week to tell us, with a picture of the "
     "parcel.", "pass"),
    ("reschedule", "Rescheduling is free, up to 2 times per parcel.",
     "pass"),
    ("reschedule", "Rescheduling is free and you can do it up to 2 times "
     "per day.", "fail"),
    ("reschedule", "Rescheduling costs $5 per change.", "fail"),
    ("delivery-windows", "Deliveries run in two-hour windows from 8:00 "
     "to 20:00, Monday to Saturday.", "pass"),
    ("delivery-windows", "We also deliver on Sundays.", "fail"),
    ("lost-parcel", "A parcel counts as lost 5 business days after its "
     "estimated delivery date.", "pass"),
    ("lost-parcel", "A parcel counts as lost after 10 business days.",
     "fail"),
    ("refund-approval", "Relay can refund up to $50 by itself; above "
     "that a person approves.", "pass"),
    ("refund-approval", "Refunds over $50 are approved automatically.",
     "fail"),
    ("address-change", "You can change the address until the parcel is "
     "out for delivery.", "pass"),
    ("address-change", "You can change the address at any time.", "fail"),
    ("free-shipping", "Orders over $60 ship free.", "pass"),
    ("free-shipping", "Orders over $40 ship free.", "fail"),
    ("support-hours", "Human agents are available from 8:00 to 20:00.",
     "pass"),
    ("support-hours", "Human agents are available around the clock.",
     "fail"),
]


def judge_verdicts(labeled=LABELED):
    """The check's verdict on each item: 'pass' if fully supported."""
    text = {d.id: d.text for d in DOCS}
    return ["pass" if groundedness(answer, text[doc]) == 1.0 else "fail"
            for doc, answer, _ in labeled]


def agreement(labeled=LABELED):
    judge, human = judge_verdicts(labeled), [h for *_, h in labeled]
    tp, fp, fn, tn = confusion(judge, human)
    tpr, tnr = tpr_tnr(judge, human)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "tpr": tpr,
            "tnr": tnr, "kappa": cohen_kappa(judge, human)}
