# When Secure-Code Repair Fails

**How AI coding agents adapt after crypto/web security feedback**

This project studies whether an AI coding agent genuinely changes its security
strategy after an independent checker rejects a security implementation, or
merely mutates parameters and repeats the same approach.

The study separates three factors: whether a task is repairable, whether checker
feedback is diagnostic or weak, and whether the agent receives frozen relevant
security guidance through a controlled RAG context. The project does not contact real
systems.

Current status: the Docker Desktop sandbox gate passes for the exact local image. An
executable local crypto/web capability catalog, independent verifiers, Ollama adapter,
and resumable pilot/main pipeline now exist. The official safety suite and the
80-task executable catalog validation pass. Two excluded Docker-backed Qwen3:4b
integration smokes completed; no pilot or main experiment has run.

For a non-technical Russian explanation of the research, the experiment design, what
the agent can and cannot see, and the exact overnight command, read
[`docs/RESEARCH_GUIDE_RU.md`](docs/RESEARCH_GUIDE_RU.md).

## Research question

> After an independent cryptographic security checker rejects an agent's code, does
> the agent change its underlying security design, or only perform surface-level
> edits and repeated attempts?

Secondary questions concern the separate effects of RAG and feedback, new
vulnerabilities, stopping after repeated failures, budget/timeout termination, and
unsupported success claims.

## Active benchmark

`benchmark/tasks/four_cell/` is the original four-cell development suite. The expanded
executable catalog is in `benchmark/tasks/executable/catalog.jsonl`:

- 12 crypto families × 4 cells = 48 records;
- 8 local web-security families × 4 cells = 32 records;
- 80 records total, validated by independent vulnerable/secure references;
- catalog/verifier version `0.5.0`;
- no network, credentials, shell, or real targets.

`RD`/`RW` are repairable; `UD`/`UW` are securely unavailable. `D` means diagnostic
feedback and `W` means weak but truthful feedback. The old generic finite-state
tasks remain only as legacy regression fixtures.

The RAG ablation uses [`benchmark/retrieval_corpus.jsonl`](benchmark/retrieval_corpus.jsonl):
20 reviewed family-level guidance documents with a frozen hash. It never contains
secure reference code, hidden condition labels, or verifier internals. Crossing RAG
on/off with the four target cells produces eight treatment arms per family.

Validate the active suite without launching an agent:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m benchmark.quality_four_cell --json
```

## Safety gate

The local Docker runner uses a digest-pinned candidate image, `--network none`, no host
mounts or credentials, dropped capabilities, bounded resources, timeouts, and forced
cleanup. On macOS Docker Desktop, the outer boundary is explicitly recorded as the
Docker Desktop LinuxKit VM; this is not daemon-level `userns-remap` and remains a
documented residual assumption.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m sandbox.safety_checks.run --json
```

The official receipt must have all checks passing before any agent execution. The
current receipt records no agent runs.

## Execution readiness

The candidate path is Docker-isolated through the approved pinned Python runtime; the
official suite validates the exact RPC path and excluded Ollama smokes have passed.
The 20-family legacy smoke batch remains engineering evidence only. The factorial
launcher runs fresh safety/catalog/RAG gates, one Docker-backed smoke, a 24-arm pilot,
and—only with explicit `--run-main`—the resumable main series. See
[`docs/OVERNIGHT_READINESS.md`](docs/OVERNIGHT_READINESS.md).

Validate the factorial design without calling Ollama:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_rag_factorial
```

Run the gated pilot and main pipeline:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.run_rag_factorial_nightly --run-main
```

The main phase starts only if the 24-arm pilot passes its integrity gate.

## Repository map

| Path | Purpose |
| --- | --- |
| `benchmark/` | Crypto/web task catalog, schemas, retrieval corpus, quality checks, and evaluator-only receipts. |
| `agent/` | Provider-neutral adapter, Ollama loopback adapter, and observable trajectory boundary. |
| `crypto_target/` | Local crypto targets, evaluator receipts, and Docker-backed smoke sandbox. |
| `sandbox/` | Local Docker policy, immutable image, and safety checks. |
| `experiments/` | Manifests, schedules, append-only attempt ledger, and raw archive contracts. |
| `analysis/` | Reproducible trajectory metrics and statistical pipeline; no eligible agent data yet. |
| `literature/` | Primary-source review, five-question paper analyses, evidence matrix, and BibTeX. |
| `paper/` | Protocol manuscript; it contains no empirical agent findings. |

## Required before data collection

1. Select a permitted provider/model and configure credentials locally; never commit or
   paste secrets.
2. Review the executable local crypto target and hidden verifier. The agent must see
   code, tools, and checker feedback, but not the oracle, condition, or verifier state.
3. Freeze prompts, model/runtime, task manifests, checker version, retrieval corpus,
   image digest, budgets, seeds, and preregistration.
4. Run the fail-closed overnight launcher. It will stop before the main series if
   safety, catalog, smoke, or pilot integrity fails.

See [docs/crypto_scope.md](docs/crypto_scope.md), [docs/CRYPTO_PROTOCOL.md](docs/CRYPTO_PROTOCOL.md),
[docs/EXPERIMENT_READINESS.md](docs/EXPERIMENT_READINESS.md), and
[docs/safety.md](docs/safety.md).
