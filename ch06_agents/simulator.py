"""A simulated customer and the loop that runs a chat against the sandbox.

In a real eval an LLM plays the customer, given a goal and a persona.
Here the customer is a few lines of script, so every run is identical."""
from ch06_agents.sandbox import call_tool


class Customer:
    """States a goal. Answers one question, if it knows the answer."""

    def __init__(self, goal, email=None):
        self.goal, self.email, self.turn = goal, email, 0

    def say(self, relay_reply):
        self.turn += 1
        if self.turn == 1:
            return self.goal
        if self.email and "verif" in (relay_reply or "").lower():
            return f"My email is {self.email}"
        return None                         # nothing left to say


def converse(agent, customer, state, max_turns=4):
    """Run one chat. The outcome is left behind in `state`."""
    session = state["session"]
    history, transcript, reply = [], [], None

    def call(name, **args):
        return call_tool(state, name, **args)

    for _ in range(max_turns):
        message = customer.say(reply)
        if message is None:
            break
        history.append(message)
        transcript.append(("customer", message))
        if state["users"][session["user"]]["email"] in message:
            session["verified"] = True      # the identity check is ours
        reply = agent(history, session, call)
        transcript.append(("relay", reply))
    return transcript
