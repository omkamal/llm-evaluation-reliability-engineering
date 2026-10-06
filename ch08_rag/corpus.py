"""A toy policy corpus: Crateway's ten policies as short, dated documents.

Everything here is invented for the book (the ten policies come from the
policy sheet; the wording around them is ours). `ALL_VERSIONS` keeps old
versions too, so we can ask "what did the documents say on this day?".
"""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Doc:
    id: str            # stable across versions: "free-shipping"
    title: str
    text: str
    version: int
    last_updated: date


def _doc(id, title, version, updated, text):
    return Doc(id, title, " ".join(text.split()), version, updated)


DOCS = [
    _doc("returns", "Returns", 3, date(2026, 6, 10), """
        You can send an unused item back to us for a return. Open the order
        in the Crateway app, choose Return item, and we will email you a
        label. Pack the item the way it arrived and hand it to the carrier.
        Returns are accepted for unused items within 14 days of delivery.
        Items that have been used cannot be returned. When your parcel
        reaches our warehouse we check it and start the refund."""),
    _doc("refund-timing", "Refund timing", 2, date(2026, 6, 10), """
        Refunds go back to the payment method you used for the order. We
        issue the refund 5 business days after the returned item is received
        at our warehouse. Your bank may need a little longer to show the
        money. If you have not seen the refund after that, ask Relay to check
        the status of your return. Refunds for damaged items follow the
        damaged-on-arrival policy."""),
    _doc("damaged", "Damaged on arrival", 2, date(2026, 3, 2), """
        If your parcel arrives damaged or the item inside is broken, tell us
        as soon as you can. Report the damage within 7 days, and include a
        photo of the item and the packaging. We will send a free replacement
        or a refund. Keep the packaging until the report is closed. You can
        make the report in the app or by asking Relay."""),
    _doc("reschedule", "Rescheduling a delivery", 1, date(2026, 1, 15), """
        You can change the day of a delivery by rescheduling it.
        Rescheduling is free, and you can do it up to 2 times per parcel.
        Each change must be made at least 48 hours before your delivery
        window starts. Open the order in the app, choose Reschedule
        delivery and pick a new day and window from the delivery windows
        on offer."""),
    _doc("delivery-windows", "Delivery windows", 1, date(2026, 1, 15), """
        We deliver in two-hour windows between 8:00 and 20:00, Monday to
        Saturday. There are no deliveries on Sunday. After you place an order
        the app shows the window for each parcel, and you get a reminder on
        the morning of delivery. Someone should be available to receive the
        parcel during the window."""),
    _doc("lost-parcel", "Lost parcels", 2, date(2026, 4, 20), """
        Parcels sometimes arrive later than the estimate. A parcel counts as
        lost 5 business days after its estimated delivery date. A claim opens
        at that point; open the order in the app to follow it. Before then,
        track the parcel in the app, because it is usually just late."""),
    _doc("refund-approval", "Refund approval", 2, date(2026, 8, 5), """
        Relay can issue a refund by itself up to $50. A refund above $50
        needs a human to approve it, so it can take longer. The reason for
        the refund is recorded with every request, and a person can review
        it later."""),
    _doc("address-change", "Changing the delivery address", 1,
         date(2026, 1, 15), """
        You can change the delivery address of an order until the parcel is
        out for delivery. Open the order in the app and edit the address, or
        ask Relay to do it. After the parcel is out for delivery the address
        is locked, so contact support if there is a mistake."""),
    _doc("free-shipping", "Free shipping", 2, date(2026, 9, 15), """
        Orders over $60 ship free. Orders of $60 or less pay the shipping
        fee shown at checkout."""),
    _doc("support-hours", "Support hours", 1, date(2026, 1, 15), """
        Human agents are available from 8:00 to 20:00. Relay, our assistant,
        answers around the clock, so you can ask a question at any time.
        Outside agent hours Relay can pass your request to a human agent,
        who will pick it up when the team is back at 8:00."""),
    _doc("help-centre", "Help centre", 1, date(2026, 1, 15), """
        Welcome to the Crateway help centre. Choose a topic to find the
        policy you need: returns, refund timing, damaged on arrival,
        rescheduling a delivery, delivery windows, lost parcels, refund
        approval, changing the delivery address, free shipping and support
        hours. Each topic has its own page. You can also ask Relay a
        question, or talk to a human agent during support hours."""),
]

# The version of "free-shipping" that was live before 15 September 2026.
OLD_FREE_SHIPPING = _doc("free-shipping", "Free shipping", 1,
                         date(2026, 1, 15), """
        Orders over $40 ship free. Orders of $40 or less pay the shipping
        fee shown at checkout.""")

ALL_VERSIONS = DOCS + [OLD_FREE_SHIPPING]


def snapshot(day):
    """The documents as they stood on `day`: newest version updated by then."""
    live = {}
    for doc in ALL_VERSIONS:
        if doc.last_updated <= day and (
                doc.id not in live or doc.version > live[doc.id].version):
            live[doc.id] = doc
    return [live[d.id] for d in DOCS]
