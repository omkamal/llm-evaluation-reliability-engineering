"""Relay-30: thirty answer-only eval cases (ten policy topics, three phrasings each).

Pass criteria are written here, before any run. `must_contain` are regular expressions the answer
must match; `must_not_contain` catches Relay volunteering an action nobody asked for.
"""
NO_ACTION = ["reschedul"]          # on every non-reschedule case, offering a reschedule is a miss


def case(cid, topic, question, must, must_not=NO_ACTION):
    return {"id": cid, "topic": topic, "question": question,
            "must_contain": must, "must_not_contain": must_not}


CASES = [
    case("R-01", "returns", "How long do I have to return an item?",
         [r"14 days"]),
    case("R-02", "returns", "Can I send something back after two weeks?",
         [r"14 days"]),
    case("R-03", "returns", "What is your return policy?", [r"14 days"]),
    case("R-04", "refund_timing", "When will I get my refund after returning an item?",
         [r"5 business days"]),
    case("R-05", "refund_timing", "How fast are refunds processed?",
         [r"5 business days"]),
    case("R-06", "refund_timing", "I returned my order; when does the money come back?",
         [r"5 business days"]),
    case("R-07", "damaged", "My parcel arrived damaged, what now?",
         [r"7 days"]),
    case("R-08", "damaged", "The item arrived broken.", [r"7 days"]),
    case("R-09", "damaged", "How do I report a damaged package?",
         [r"7 days"]),
    case("R-10", "reschedule", "Can I reschedule my delivery?",
         [r"2 times|twice"], []),
    case("R-11", "reschedule", "How many times can I change the delivery date?",
         [r"2 times|twice"], []),
    case("R-12", "reschedule", "I need a different delivery day.",
         [r"2 times|twice"], []),
    case("R-13", "windows", "What are the delivery windows?",
         [r"Monday to Saturday"]),
    case("R-14", "windows", "What time will my parcel arrive?",
         [r"Monday to Saturday"]),
    case("R-15", "windows", "Do you deliver on Sundays?",
         [r"Monday to Saturday"]),
    case("R-16", "lost", "My parcel is late, is it lost?",
         [r"5 business days"]),
    case("R-17", "lost", "When is a parcel considered lost?",
         [r"5 business days"]),
    case("R-18", "lost", "How do I claim a lost package?",
         [r"5 business days"]),
    case("R-19", "refund_limit", "Is there a limit on automatic refunds?",
         [r"\$50"]),
    case("R-20", "refund_limit", "Why does my big refund need approval?",
         [r"\$50"]),
    case("R-21", "refund_limit", "Do large refunds need a person?",
         [r"\$50"]),
    case("R-22", "address", "Can I change my delivery address?",
         [r"out for delivery"]),
    case("R-23", "address", "I moved; update the address on my order.",
         [r"out for delivery"]),
    case("R-24", "address", "Wrong address on my order, help?",
         [r"out for delivery"]),
    case("R-25", "shipping", "Is shipping free?", [r"\$60"]),
    case("R-26", "shipping", "What is the minimum order for free shipping?",
         [r"\$60"]),
    case("R-27", "shipping", "How much do I need to spend to avoid shipping fees?",
         [r"\$60"]),
    case("R-28", "support", "Can I talk to a person?", [r"8:00"]),
    case("R-29", "support", "What are your support hours?", [r"8:00"]),
    case("R-30", "support", "Is anyone available at night?", [r"8:00"]),
]
