# LLM Evaluation & Reliability Engineering: companion code

Runnable code for the book *LLM Evaluation & Reliability Engineering* by Omar Kamal Hosney.

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
| `ch08_rag/` | A BM25 retriever, chunking, retrieval metrics (recall@k, MRR, context precision), grounding and citation checks, a triage sheet, an index-lifecycle check, an access filter and a chunk-size sweep |
| `ch09_when_calls_fail/` | Retry with jitter and `Retry-After`, a shared retry budget, a circuit breaker, a step guard, a loop guard and a quota manager |
| `ch10_providers/` | A provider adapter and router with eligibility filters (data residency), health ranking, capacity-aware failover with hysteresis, service tiers, streaming that survives a cut, cancellation that reaches every layer, and one request through the whole path |
| `ch11_traces/` | A small tracer (spans, context, `traceparent` handoffs, links), six span types, a traced context trim, tail sampling, redaction, a trace-cost estimate and trace shrinking; `optional/` holds an OpenTelemetry snippet that CI does not run |
| `ch12_slos/` | Per-task SLIs, a judged-sample SLI with its interval, one SLO sheet with two layers, error budget and burn-rate alerts over two windows, deep dependency checks and a one-page report; `optional/` holds Prometheus rules that CI does not run |
| `ch13_drift/` | Segment-aware baseline bands, drift-probe sets (with the judge's own), PSI, chi-square and Kolmogorov-Smirnov tests, RAG drift, and alert routing with precision; `optional/` holds an Evidently snippet that CI does not run |
| `ch14_cost/` | Token economics and the quadratic cost of history, cost per resolved task, FinOps showback and forecasting, cascades and routers, prompt and semantic caches, parallel latency, capacity and provisioning, and a paired proof that a saving keeps quality; `optional/` holds a LiteLLM snippet that CI does not run |
| `ch15_cicd/` | A miniature prompts-as-code repository, path filters and eval tiers, the non-inferiority gate with a never-fail floor and slice limits, the gate's own A/A check, flaky-case quarantine, an eval cache, run records and bisect, the contamination guard, and the GitHub Actions workflow `workflows/evals.yml`; `optional/` holds DeepEval, promptfoo, Inspect and Ragas snippets that CI does not run |
| `ch16_release/` | Shadow comparison, a canary controller with guard metrics and automatic rollback, a `FaultyProvider` rehearsal, the error-budget release check, release bundles with fingerprints, a migration runbook, a model scorecard, and the model-upgrade capstone |
| `ch17_security/` | A guard chain (belt, tier, schema, session, owner, limit) with ownership taken from the session, a toy injection screen, a red-team set with benign twins and intervals, memory-poisoning rules, secret and tool-pin checks; `optional/` holds a Guardrails AI snippet that CI does not run |
| `ch18_governance/` | A scoped, short-lived credential broker, an audit trail sealed with a keyed hash (HMAC) and reconciled by coverage, an inventory and change control, a compliance map as data, expected-loss review routing, context packets, and a rubber-stamp detector; `optional/` holds a LangGraph snippet that CI does not run |
| `ch19_incidents/` | Kill-switch and version-pin flags, a runbook that climbs the containment ladder, a ledger with compensating actions, recovery checks against baseline bands, a status-update lint and a postmortem record check; `optional/` holds an OpenFeature snippet that CI does not run |
| `ch20_program/` | A RACI sheet checked against a roster, a pager-load report, a runbook freshness audit, a three-verdict readiness scorecard, a maturity placement, a findings tracker and a quarterly report that refuses any line not labelled measured or assumed |
| `common/` | The scripted Relay stand-in and a fake clock, so a 30-second cooldown takes zero seconds in tests |

Chapters 1 to 20 each have a folder here, and the folder name starts with the chapter number (the prologue has no code).

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # pydantic, pytest, PyYAML
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
.venv/bin/python -m ch10_providers.demo         # Chapter 10: routing, failover, tiers, streams, cancellation
.venv/bin/python -m ch11_traces.demo            # Chapter 11: span trees, handoffs, sampling, cost
.venv/bin/python -m ch12_slos.demo              # Chapter 12: SLO sheet, error budget, burn-rate alerts
.venv/bin/python -m ch13_drift.demo             # Chapter 13: bands, drift tests, probe sets, alert routing
.venv/bin/python -m ch14_cost.demo              # Chapter 14
.venv/bin/python -m ch15_cicd.demo              # Chapter 15
.venv/bin/python -m ch16_release.demo           # Chapter 16
.venv/bin/python -m ch17_security.demo          # Chapter 17
.venv/bin/python -m ch18_governance.demo        # Chapter 18
.venv/bin/python -m ch19_incidents.demo         # Chapter 19
.venv/bin/python -m ch20_program.demo           # Chapter 20
```

Python 3.10 or newer. Chapter 2 uses [Pydantic](https://docs.pydantic.dev/) (`pip install -r requirements.txt`) and Chapter 5 reuses that gateway; everything else uses only the standard library. Files under `optional/` folders show a vendor library (OpenTelemetry, Prometheus, Evidently); they are not run by the tests or by CI, and each states the version it was checked with.
Continuous integration runs the tests and the demos on Python 3.10 to 3.13.

## License

MIT. See [LICENSE](LICENSE).
