# When to Stop: AI Agents After Failed Security Actions

This repository is the local research infrastructure for **“When to Stop: How AI Agents Adapt After Failed Attacks and Why They Fail to Give Up.”** The goal is to distinguish recovery, repetition, strategy change, stopping, and unsupported success claims after negative evidence in intentionally local security tasks.

**Current status:** no provider-backed pilot or main experiment has been run. The nine-task finite-state suite is an engineering pilot; the sole recorded trajectory is a deterministic scripted fixture, excluded from research analysis. [Analysis results](analysis/results.md) correctly report **0 eligible main runs** and no estimable behavioral effect. [The manuscript](paper/final.md) is a protocol/implementation audit, not an empirical findings paper. The runtime Docker safety gate is fail-closed until a reviewed immutable image exists and every required check passes.

## Project map

| Area | Purpose |
| --- | --- |
| `benchmark/` | Nine versioned local pilot tasks, schemas, static quality checks, and evaluator-owned finite-state verifiers. |
| `agent/` | Provider-neutral adapter contract, public-task projection, scripted test double, and episode runner. No real provider adapter yet. |
| `sandbox/` | Locked Docker policy, runner, candidate image template, and fail-closed safety checks. |
| `experiments/` | Manifest/trajectory schemas, observable logging, integrity checks, and excluded engineering fixture. |
| `analysis/`, `tables/`, `figures/stopping_experiment/` | Reproducible analysis code and derived zero-data audit outputs. No empirical figures. |
| `docs/` | Preregistration draft, benchmark and safety design, readiness, peer review, and reproducibility notes. |
| `literature/`, `paper/` | Primary-source literature review and honest protocol manuscript. |

## Reproduce the available checks

Run from the repository root using Python 3 and its standard library. These commands do not call model providers or public targets. `analysis.pipeline audit` regenerates only derived zero-data outputs and now refuses to overwrite a locked empirical analysis.

```bash
python3 --version
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m benchmark.quality --json
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.validate_artifacts \
  --manifest experiments/manifests/e2e-local-finite-state-v0.1.2.json \
  --log experiments/runs/e2e-local-finite-state-v0.1.2/fixture-run-0001.jsonl \
  --receipt experiments/runs/e2e-local-finite-state-v0.1.2/fixture-run-0001.receipt.json --json
PYTHONDONTWRITEBYTECODE=1 python3 -B -m analysis.pipeline --json audit
```

The inspected fixture is harmless scripted evidence, not an AI-agent result. Its raw log SHA-256 is `7de80aa43ed0feefb2ab88f67ec7d634dd4688b583b8fd39db19109b9e310c8b`. Generated raw runs are ignored by Git by default; only this inspected fixture is included in the baseline explicitly so the integrity check is reproducible. Do not treat a unit test or reference plan as evidence of model competence.

The Docker safety suite is a separate hard gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m sandbox.safety_checks.run --json
```

A nonzero exit means **do not run an agent**. No `NOT_RUN` check may be counted as `PASS`. The approved-image allow-list remains empty until image provenance and containment are independently validated; [readiness](docs/EXPERIMENT_READINESS.md) and [blockers](docs/BLOCKERS.md) record the current gate status.

## What is needed for an empirical reproduction

Before any pilot: reconcile the three-condition engineering suite with the four-cell [preregistration draft](docs/preregistration.md); independently review task reachability, distractor plausibility, difficulty, and verifiers; freeze Git revision, image digest, task/verifier versions, agent/harness, prompts, model and provider settings, budget and seeds; pass all runtime safety checks. Each real run must preserve an immutable manifest, raw observable trajectory, verifier receipt, and error classification. Only an explicitly verified [analysis input lock](analysis/README.md) may produce paper numbers and figures. The target remains local and network-isolated; no real credentials, public IPs, or third-party services are permitted.

The prior AVB-Bench manuscript and presentation materials were moved to a recoverable macOS Trash archive at `/Users/imranmzakirov/.Trash/when-to-stop-legacy-avb-2026-09-29/`; they are not part of this study or Git baseline. See [cleanup record](docs/LEGACY_CLEANUP.md). No raw research data were deleted.
