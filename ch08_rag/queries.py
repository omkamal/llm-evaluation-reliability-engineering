"""50 labeled retrieval queries: which document(s) hold the answer?

A query is *answerable* when `gold` names at least one document. `must` are
the facts a correct answer has to state (written before any run, as in
Chapter 3). Fact recall credits a fact wherever it appears, so each is
worded to appear on no wrong page that comes back (a test checks).
Unanswerable queries have no gold document: the right answer is "I don't
know". The queries were written beside the pages, which flatters any
search; real ones come from customers (Chapter 7).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    id: str
    text: str
    gold: tuple          # ids of the documents that contain the answer
    must: tuple = ()     # facts the answer has to state

    @property
    def answerable(self):
        return bool(self.gold)


def q(id, text, gold, *must):
    return Query(id, text, tuple(gold.split()), must)


QUERIES = [
    # Chapter 3's thirty questions, now labeled with where the answer lives
    q("Q01", "How long do I have to return an item?", "returns", "14 days"),
    q("Q02", "Can I send something back after two weeks?", "returns",
      "14 days"),
    q("Q03", "What is your return policy?", "returns", "14 days"),
    q("Q04", "When will I get my refund after returning an item?",
      "refund-timing", "5 business days"),
    q("Q05", "How fast are refunds processed?", "refund-timing",
      "5 business days"),
    q("Q06", "I returned my order; when does the money come back?",
      "refund-timing", "5 business days"),
    q("Q07", "My parcel arrived damaged, what now?", "damaged", "7 days"),
    q("Q08", "The item arrived broken.", "damaged", "7 days"),
    q("Q09", "How do I report a damaged package?", "damaged", "7 days"),
    q("Q10", "Can I reschedule my delivery?", "reschedule", "2 times"),
    q("Q11", "How many times can I change the delivery date?", "reschedule",
      "2 times"),
    q("Q12", "I need a different delivery day.", "reschedule", "2 times"),
    q("Q13", "What are the delivery windows?", "delivery-windows",
      "Monday to Saturday"),
    q("Q14", "What time will my parcel arrive?", "delivery-windows",
      "Monday to Saturday"),
    q("Q15", "Do you deliver on Sundays?", "delivery-windows",
      "Monday to Saturday"),
    q("Q16", "My parcel is late, is it lost?", "lost-parcel",
      "5 business days"),
    q("Q17", "When is a parcel considered lost?", "lost-parcel",
      "5 business days"),
    q("Q18", "How do I claim a lost package?", "lost-parcel",
      "5 business days"),
    q("Q19", "Is there a limit on automatic refunds?", "refund-approval",
      "$50"),
    q("Q20", "Why does my big refund need approval?", "refund-approval",
      "$50"),
    q("Q21", "Do large refunds need a person?", "refund-approval", "$50"),
    q("Q22", "Can I change my delivery address?", "address-change",
      "out for delivery"),
    q("Q23", "I moved; update the address on my order.", "address-change",
      "out for delivery"),
    q("Q24", "Wrong address on my order, help?", "address-change",
      "out for delivery"),
    q("Q25", "Is shipping free?", "free-shipping", "$60"),
    q("Q26", "What is the minimum order for free shipping?", "free-shipping",
      "$60"),
    q("Q27", "How much do I need to spend to avoid shipping fees?",
      "free-shipping", "$60"),
    q("Q28", "Can I talk to a person?", "support-hours", "8:00 to 20:00"),
    q("Q29", "What are your support hours?", "support-hours",
      "8:00 to 20:00"),
    q("Q30", "Is anyone available at night?", "support-hours",
      "8:00 to 20:00"),
    # eight harder phrasings: different words for the same ideas
    q("Q31", "Can I still return something I bought last week?", "returns",
      "14 days"),
    q("Q32", "Money back for a smashed item?", "damaged", "7 days"),
    q("Q33", "Is there a fee to move my delivery to another day?",
      "reschedule", "Rescheduling is free"),
    q("Q34", "How many hours long is a delivery window?",
      "delivery-windows", "two-hour"),
    q("Q35", "At what amount does a refund need sign-off?",
      "refund-approval", "$50"),
    q("Q36", "My order has not shown up; when can I open a claim?",
      "lost-parcel", "5 business days"),
    q("Q37", "Does an order of $75 ship free?", "free-shipping", "$60"),
    q("Q38", "Can the address change once the courier has the parcel?",
      "address-change", "out for delivery"),
    # five questions whose answer needs two documents, and one that looks like
    # it does (Q41: the rescheduling page is a decoy)
    q("Q39", "I want to return an item and get my money back: how long do I "
      "have, and when does the refund arrive?", "returns refund-timing",
      "14 days", "5 business days"),
    q("Q40", "Is a refund for a damaged parcel automatic, and how long do "
      "I have to report it?", "damaged refund-approval", "7 days", "$50"),
    q("Q41", "Can I reschedule a delivery to a Sunday?",
      "delivery-windows", "Monday to Saturday"),
    q("Q42", "My parcel is lost and I want an $80 refund: what happens?",
      "lost-parcel refund-approval", "5 business days", "$50"),
    q("Q43", "It is late evening and my parcel is lost: who can help?",
      "lost-parcel support-hours", "5 business days", "8:00 to 20:00"),
    q("Q44", "Is my order eligible for free shipping, and can I still "
      "change the address?", "free-shipping address-change", "$60",
      "out for delivery"),
    # six questions the documents cannot answer
    q("Q45", "Do you deliver to other countries?", ""),
    q("Q46", "Can I pay with cryptocurrency?", ""),
    q("Q47", "What is the warranty on electronics?", ""),
    q("Q48", "Do you have a loyalty programme?", ""),
    q("Q49", "Where is your head office?", ""),
    q("Q50", "Can I get an invoice for my order?", ""),
]
