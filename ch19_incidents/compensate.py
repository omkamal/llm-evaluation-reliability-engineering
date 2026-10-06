"""Compensating actions on the Chapter 6 sandbox.

A credit that has gone out cannot be rolled back: the customer may have
spent it. We add a ledger beside the sandbox's records, never edit a
line of it, and answer the credit with a new line of its own. Taking
money back from a customer is Finance's decision, never automatic."""


class NeedsFinance(PermissionError):
    """A reversal was asked for with no one in Finance approving it."""


def open_ledger(state, owners, opening):
    """owners: order id -> customer. opening: customer -> cents held."""
    state["owner"] = dict(owners)
    state["ledger"] = []
    for who, cents in opening.items():
        post(state, "opening", who, cents, None, f"open:{who}")
    return state


def post(state, kind, who, cents, ref, key):
    """Append one line. A key already seen posts nothing (Chapter 2)."""
    for line in state["ledger"]:
        if line["key"] == key:
            return line["id"]
    line = {"id": f"L-{len(state['ledger']) + 1:03d}", "kind": kind,
            "who": who, "cents": cents, "ref": ref, "key": key}
    state["ledger"].append(line)
    return line["id"]


def balance(state, who):
    """What the customer holds. Owed lines are a claim, not money."""
    return sum(x["cents"] for x in state["ledger"]
               if x["who"] == who and x["kind"] != "owed")


def issue_refund(state, order_id, cents, key):
    state["audit_log"].append(
        {"tool": "issue_refund", "target": order_id})
    return post(state, "credit", state["owner"][order_id], cents,
                order_id, key)


def spend(state, who, cents, key):
    """The customer uses some of what they hold."""
    return post(state, "spend", who, -cents, None, key)


def spent_since(state, credit):
    """Spending after the credit counts against the credit first, so a
    reversal takes back what is left of it, never the customer's own
    money (Finance may choose otherwise; the code never does)."""
    later = state["ledger"][state["ledger"].index(credit) + 1:]
    return -sum(x["cents"] for x in later
                if x["who"] == credit["who"] and x["kind"] == "spend")


def reverse_credit(state, credit_id, key, approved_by=""):
    """Take back what is left of the credit; record the rest as owed.
    Nothing posts without a named approver in Finance. Safe to run
    twice: the same key changes nothing the second time."""
    if not approved_by:
        raise NeedsFinance(credit_id)        # never automatic
    credit = next(x for x in state["ledger"] if x["id"] == credit_id)
    if not any(x["key"] == key for x in state["ledger"]):
        state["audit_log"].append({"tool": "reverse_credit",
                                   "target": credit_id,
                                   "approved_by": approved_by})
        take = max(credit["cents"] - spent_since(state, credit), 0)
        if take:
            post(state, "reversal", credit["who"], -take, credit_id, key)
        if credit["cents"] > take:
            post(state, "owed", credit["who"], credit["cents"] - take,
                 credit_id, key + ":owed")
    return outcome(state, credit_id)


def outcome(state, credit_id):
    lines = [x for x in state["ledger"] if x["ref"] == credit_id]
    return {"recovered": -sum(x["cents"] for x in lines
                              if x["kind"] == "reversal"),
            "owed": sum(x["cents"] for x in lines if x["kind"] == "owed")}
