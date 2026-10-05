"""Invented questions for the semantic-cache sweep, with true intents.

CACHED: the intents already in the cache, as (intent, question, answer).
ASKED: new questions as (intent, text). A question whose intent is in
CACHED should hit; any other intent should miss, even when the words
look alike.
"""
CACHED = [
    ("returns", "How many days do I have to return an unused item?",
     "Within 14 days of delivery."),
    ("damaged", "How long do I have to report a damaged parcel?",
     "Within 7 days, with a photo."),
    ("reschedule", "How many times can I reschedule a delivery?",
     "Twice per parcel, at least 48 hours ahead."),
    ("refund_timing", "How long until my refund arrives after a return?",
     "5 business days after we receive the item."),
    ("refund_limit", "What is the largest refund Relay can issue itself?",
     "$50; above that a person approves."),
    ("free_shipping", "What order total gets free shipping?",
     "Orders over $60."),
    ("lost", "When does a parcel count as lost?",
     "5 business days after its estimated delivery date."),
    ("windows", "What hours are the delivery windows?",
     "8:00 to 20:00, Monday to Saturday."),
    ("address", "Can I change my delivery address?",
     "Until the parcel is out for delivery."),
]

ASKED = [
    # the same intents in other words: a hit is right
    ("returns", "How long do I have to send back an unused item?"),
    ("returns", "What is the return window for unused items?"),
    ("damaged", "How many days to report a damaged parcel?"),
    ("damaged", "How long do I have to report my parcel arrived damaged?"),
    ("reschedule", "How often can I reschedule my delivery?"),
    ("reschedule", "How many times can a delivery be rescheduled?"),
    ("refund_timing", "How long until I get my refund after a return?"),
    ("refund_timing", "When does my refund arrive after returning it?"),
    ("refund_limit", "What is the biggest refund Relay can issue itself?"),
    ("refund_limit", "Largest refund Relay can issue by itself?"),
    ("free_shipping", "What order total is needed for free shipping?"),
    ("free_shipping", "Which order total gets free shipping?"),
    ("lost", "When is a parcel counted as lost?"),
    ("lost", "When does my parcel count as lost?"),
    ("windows", "What hours do the delivery windows run?"),
    ("windows", "What are the delivery window hours?"),
    ("address", "Can I change the delivery address of my order?"),
    ("address", "Can I change my delivery address?"),
    # other intents with similar words: a hit is a false hit
    ("returns_used", "How many days do I have to return a used item?"),
    ("returns_damaged", "How many days do I have to return a damaged item?"),
    ("damaged_no_photo",
     "How long do I have to report a damaged parcel without a photo?"),
    ("pickup", "How many times can I reschedule a return pickup?"),
    ("refund_cancel", "How long until my refund arrives after a cancel?"),
    ("approve_limit", "What is the largest refund a person can approve?"),
    ("free_returns", "What order total gets free returns?"),
    ("delivered", "When does a parcel count as delivered?"),
    ("support_hours", "What hours are the support windows?"),
    ("billing_address", "Can I change my billing address?"),
    ("address_late",
     "Can I change my delivery address once it is out for delivery?"),
    ("free_shipping_40", "Is shipping free over $40?"),
]
