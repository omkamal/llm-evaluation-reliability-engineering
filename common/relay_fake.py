"""A scripted stand-in for Relay, so every example in the book runs offline.

`ask(question, version)` is the one seam: in a real system you would call your model here.
  v1  the current Relay: correct on the topics it recognises, hands off to a human otherwise.
  v2  "the Friday tweak": a prompt change meant to make Relay more proactive. It volunteers a
      reschedule offer on delivery-window questions and has started to invent the return window.
"""

# (topic, keywords that trigger it, v1 answer). Order matters: first match wins.
TOPICS = [
    ("damaged", ["damaged", "broken"],
     "Report it within 7 days with a photo and we will send a free replacement or a refund."),
    ("refund_limit", ["limit on automatic", "need approval", "large refund"],
     "Refunds up to $50 are automatic; above $50 a person approves them."),
    ("refund_timing", ["refund"],
     "Refunds are issued 5 business days after we receive the returned item."),
    ("returns", ["return"],
     "You can return unused items within 14 days of delivery."),
    ("reschedule", ["reschedul", "change the delivery date", "different delivery day"],
     "Rescheduling is free, up to 2 times per parcel, at least 48 hours before your window."),
    ("windows", ["delivery window", "what time will my parcel", "deliver on"],
     "Deliveries run in two-hour windows between 8:00 and 20:00, Monday to Saturday."),
    ("lost", ["lost", "claim"],
     "A parcel counts as lost 5 business days after its estimated delivery date, and a claim opens then."),
    ("address", ["address"],
     "You can change the address until the parcel is out for delivery."),
    ("shipping", ["shipping"],
     "Shipping is free on orders over $60."),
    ("support", ["person", "support hours", "anyone available"],
     "Human agents are available 8:00 to 20:00; I am here around the clock."),
]
FALLBACK = "I am not sure about that. Let me connect you with a human agent."


def ask(question: str, version: str = "v1") -> str:
    q = question.lower()
    for topic, keywords, answer in TOPICS:
        if any(k in q for k in keywords):
            if version == "v2":                       # the Friday tweak
                if topic == "returns":
                    return "You can return items within 30 days of delivery."
                if topic == "windows":
                    return answer + " Shall I reschedule your delivery for you now?"
            return answer
    return FALLBACK
