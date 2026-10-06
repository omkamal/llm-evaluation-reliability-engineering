"""A simulated customer and the loop that runs a chat against the sandbox.

In a real eval an LLM plays the customer, given a goal and an identity.
Here the customer is a few lines of script, so every run is identical.

Identity is the harness's job, never Relay's and never the customer's
word: the harness emails a one-time code to the address on file, and the
session is verified only when that code comes back. Typing an email
address proves nothing, because anyone can know one."""
import random
from types import MappingProxyType

from ch06_agents.sandbox import call_tool


class Customer:
    """States a goal. Answers one question, if it knows the answer.
    `email` is the mailbox this customer can read."""

    def __init__(self, goal, email=None):
        self.goal, self.email, self.turn = goal, email, 0
        self.inbox = []                     # codes mailed to `email`

    def say(self, relay_reply):
        self.turn += 1
        if self.turn == 1:
            return self.goal
        if self.inbox and "code" in (relay_reply or "").lower():
            return f"The code is {self.inbox[-1]}"
        return None                         # nothing left to say


def one_time_code(user):
    """Six digits, fixed per user so that every run is identical."""
    return f"{random.Random(user).randrange(10 ** 6):06d}"


def converse(agent, customer, state, max_turns=4):
    """Run one chat. The outcome is left behind in `state`."""
    session = state["session"]
    code = None
    if not session["verified"]:             # email a one-time code to
        code = one_time_code(session["user"])   # the address on file
        on_file = state["users"][session["user"]]["email"]
        if customer.email == on_file:
            customer.inbox.append(code)     # only its owner reads it
    view = MappingProxyType(session)        # Relay may read, not write
    history, transcript, reply = [], [], None

    def call(name, **args):
        return call_tool(state, name, **args)

    for _ in range(max_turns):
        message = customer.say(reply)
        if message is None:
            break
        history.append(message)
        transcript.append(("customer", message))
        if code and code in message.split():
            session["verified"] = True      # the code came back
        reply = agent(history, view, call)
        transcript.append(("relay", reply))
    return transcript
