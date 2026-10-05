"""Scripted conversations with the expert's verdict (illustrative)."""


def conv(cid, expert, turns, reopened=None):
    rows = [{"who": w, "text": t} for w, t in turns]
    return {"id": cid, "expert": expert, "turns": rows,
            "reopened_after_hours": reopened}


CONVERSATIONS = [
    conv("s1", "miss", [("customer", "Where is ORD-004829?"),
                        ("relay", "Your order shipped on Monday."),
                        ("customer", "Where is order ORD-004829 now?")]),
    conv("s2", "miss", [("customer", "How long to return a jacket?"),
                        ("relay", "You have 30 days."),
                        ("customer", "Can I talk to a real person?")]),
    conv("s3", "miss", [("customer", "Move my delivery to Thursday."),
                        ("relay", "Done, Thursday morning.")], reopened=20),
    conv("s4", "ok", [("customer", "Can I speak to someone about a bulk "
                       "order for my shop?"),
                      ("relay", "Human agents are in 8:00 to 20:00. I "
                       "have passed your request on.")]),
    conv("s5", "ok", [("customer", "What are your support hours?"),
                      ("relay", "Human agents work 8:00 to 20:00.")],
         reopened=70),
    conv("s6", "ok", [("customer", "Do you ship to Canada?"),
                      ("relay", "Yes, shipping is free over $60.")]),
    conv("s7", "ok", [("customer", "Where is my parcel?"),
                      ("relay", "Which order do you mean?"),
                      ("customer", "Where is my parcel? It is ORD-004829."),
                      ("relay", "It is out for delivery.")]),
    conv("s8", "miss", [("customer", "How long do I have to return an "
                         "item?"),
                        ("relay", "You can return items within 30 days."),
                        ("customer", "Great, thanks.")]),
    conv("s9", "miss", [("customer", "Can I change my delivery address?"),
                        ("relay", "Shipping is free on orders over $60."),
                        ("customer", "Can I change my delivery address "
                         "please?"),
                        ("relay", "Shipping is free on orders over $60."),
                        ("customer", "Get me a real person.")]),
]
