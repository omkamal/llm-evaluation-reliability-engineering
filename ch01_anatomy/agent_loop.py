"""The agent loop: the model decides, a tool runs, the result goes back, and it decides again."""

MAX_STEPS = 12


def run_agent(user_message, model, tools, max_steps=MAX_STEPS):
    history = [("user", user_message)]
    for _ in range(max_steps):
        action = model(history)   # ("tool", ...) or ("answer", text)
        if action[0] == "answer":
            return action[1], history
        _, name, args = action
        history.append(("tool_call", f"{name}({args})"))
        history.append(("tool_result", tools[name](**args)))
    return "I could not finish this; connecting you to a person.", history
