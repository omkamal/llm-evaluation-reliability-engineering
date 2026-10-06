"""Run one trial of one case, and grade it two ways: by the reply, and
by the state of the sandbox."""
import copy
import re

from ch06_agents.sandbox import new_state
from ch06_agents.simulator import Customer, converse
from ch06_agents.state_check import check_state, check_untouched


def run_case(agent, case, customer=None):
    """One trial in a fresh sandbox. Returns the evidence."""
    state = new_state(case["k"], dict(case["session"]))
    before = copy.deepcopy(state)
    customer = customer or Customer(case["message"], case["email"])
    transcript = converse(agent, customer, state)
    return {"before": before, "after": state, "transcript": transcript}


def reply_ok(case, run):
    """Final-answer grading, a keyword test as in Chapter 3: does the last
    message say the right thing, without denying it?"""
    last = run["transcript"][-1][1]
    deny = case.get("must_not")
    return (re.search(case["says"], last, re.I) is not None
            and not (deny and re.search(deny, last, re.I)))


def state_problems(case, run):
    """State-based grading: did the world end up right? {} means yes."""
    if case["exp"] is None:
        return check_untouched(run["before"], run["after"])
    return check_state(run["before"], run["after"], case["exp"])


def passed(case, run):
    """A trial passes when the world is right AND the words are right."""
    return not state_problems(case, run) and reply_ok(case, run)
