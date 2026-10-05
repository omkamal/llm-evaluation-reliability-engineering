# LLM Evaluation & Reliability Engineering: companion code

Runnable code for the book *LLM Evaluation & Reliability Engineering* by Omar Kamal.

Everything runs **offline**: no API key, no network, no cost. `common/relay_fake.py` is a scripted stand-in for the
Relay assistant used throughout the book. It exposes one function, `ask(question, version)`, and that is the single
line you would replace with a call to your own model.

| Folder | What it contains |
|---|---|
| `ch01_anatomy/` | A metered model call, sampling, a context window that silently drops turns, and the agent loop |
| `ch02_trust_outputs/` | A Pydantic ticket schema, the validation gateway, a capped repair loop, truncation triage, four-layer tool-call checks and an idempotent refund |
| `ch03_first_eval/` | A 30-case eval ("Relay-30"), a code grader, and a pytest gate that catches a regression |
| `ch09_when_calls_fail/` | Retry with jitter and `Retry-After`, a shared retry budget, a circuit breaker, a step guard, a loop guard and a quota manager |
| `common/` | The scripted Relay stand-in and a fake clock, so a 30-second cooldown takes zero seconds in tests |

More chapters will be added as the book is written.

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # pydantic and pytest
.venv/bin/python -m pytest -q                    # all tests
.venv/bin/python -m ch01_anatomy.demo            # Chapter 1 numbers
.venv/bin/python -m ch02_trust_outputs.demo      # Chapter 2: validation, repair, tool contracts, idempotency
.venv/bin/python -m ch03_first_eval.run_evals v1 # score Relay v1 against the 30 cases
.venv/bin/python -m ch03_first_eval.run_evals v2 # score the "Friday tweak" version
.venv/bin/python -m ch09_when_calls_fail.demo    # every Chapter 9 defence, with printed output
```

Python 3.10 or newer. Chapter 2 uses [Pydantic](https://docs.pydantic.dev/) (`pip install -r requirements.txt`); everything else uses only the standard library.
Continuous integration runs the tests and the demos on Python 3.10 to 3.13.

## License

MIT. See [LICENSE](LICENSE).
