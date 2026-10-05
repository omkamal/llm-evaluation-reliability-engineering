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
| `ch04_numbers/` | pass@k and pass^k, standard errors and 95% intervals, sample-size planning, clustered errors, the bootstrap, paired comparison, a noisy Relay stand-in and the eval report card |
| `ch05_judge/` | A simulated LLM judge with five biases, the fixes, agreement and Cohen's kappa, a calibration loop, a jury, and the judge's cost in production |
| `ch06_agents/` | A tool sandbox, state checks, trigger and non-trigger cases (Relay-60), trajectory and policy graders, a simulated customer, a crew with a lossy handoff, and a paired version comparison |
| `ch07_datasets/` | Stratified sampling, dataset cards with a content hash, a contamination guard, double-labeling and kappa, online sampling, implicit-feedback hints, redaction and a test-tenant guard |
| `ch08_rag/` | A BM25 retriever, chunking, retrieval metrics (recall@k, MRR, context precision), grounding and citation checks, a triage sheet, an index-lifecycle check and a chunk-size sweep |
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
.venv/bin/python -m ch04_numbers.demo           # Chapter 4: error bars, bootstrap, paired comparison, report card
.venv/bin/python -m ch05_judge.demo             # Chapter 5: judge biases, fixes, kappa, calibration, jury
.venv/bin/python -m ch06_agents.demo            # Chapter 6: state checks, trigger rates, trajectories, crew
.venv/bin/python -m ch07_datasets.demo          # Chapter 7: sampling, dataset card, labeling, redaction
.venv/bin/python -m ch08_rag.demo               # Chapter 8: retrieval metrics, grounding, triage, index lifecycle
.venv/bin/python -m ch09_when_calls_fail.demo    # every Chapter 9 defence, with printed output
```

Python 3.10 or newer. Chapter 2 uses [Pydantic](https://docs.pydantic.dev/) (`pip install -r requirements.txt`) and Chapter 5 reuses that gateway; everything else uses only the standard library.
Continuous integration runs the tests and the demos on Python 3.10 to 3.13.

## License

MIT. See [LICENSE](LICENSE).
