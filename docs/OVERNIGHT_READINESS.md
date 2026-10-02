# Overnight readiness: factorial RAG study

**Updated:** 2026-10-02
**Scientific data collected:** none yet. Existing smoke traces are excluded.

## Current architecture

The active executable catalog contains 80 local targets: 48 crypto and 32 web task
definitions across 20 families and four cells (`RD/UD/RW/UW`). Candidate Python source
runs only inside the digest-pinned Docker candidate runtime with no network, host
mounts, credentials, or external targets.

The revised study adds a controlled retrieval factor without modifying those targets:

- `off`: the retrieval query and corpus hash are recorded, but no document is shown;
- `relevant`: one reviewed family-level security guidance document is shown.

The 20-document corpus is `benchmark/retrieval_corpus.jsonl`. It contains no secure
reference code, condition labels, expected outcomes, or verifier internals.

## Gated sequence

`experiments.run_rag_factorial_nightly` performs:

1. Ollama/model preflight;
2. 80-target catalog validation;
3. retrieval-corpus coverage and leakage checks;
4. Docker image mapping and complete runtime safety suite;
5. one excluded provider/Docker smoke;
6. a 24-arm pilot: 3 families × 4 target cells × RAG on/off;
7. pilot log/receipt/infrastructure integrity gate;
8. main only when `--run-main` was explicitly supplied and every prior gate passed.

Any failure stops the pipeline. The launcher never weakens the sandbox or silently
relabels infrastructure failure as agent failure.

## Commands

Static validation only:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_rag_factorial
```

Pilot only:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.run_rag_factorial_nightly
```

Pilot followed by main after a clean gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.run_rag_factorial_nightly --run-main
```

The full main upper bound is 160 treatment arms × 3 repeats = 480 episodes. On an M1
MacBook Air with a 4B local model this can take much longer than one night. The process
is resumable: rerunning the exact same command uses the frozen manifest, schedule, and
attempt ledger and skips completed slots.

## Where results appear

- live terminal events: `START` and `FINISH` JSON records;
- nightly status: `experiments/nightly/rag-*.json`;
- pilot summary: `experiments/reports/rag-factorial-pilot-0-5-0.json`;
- main summary: `experiments/reports/rag-factorial-main-0-5-0.json`;
- immutable raw archive: `experiments/raw_archive/rag-factorial-*`;
- manifests and schedules: `experiments/manifests/` and `experiments/schedules/`.

Raw trajectories and generated result files are intentionally ignored by Git. They
must be backed up separately after collection and must never be overwritten.
