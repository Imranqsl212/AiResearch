# Overnight readiness: factorial RAG study

> **Historical plan, 2 October 2026.** This documents an earlier 24-arm pilot
> and 480-episode upper-bound design. It is not the prospective v1 release
> schedule or a current launch guide. The completed exploratory cohort has 40
> episodes; the separate AEAD and corrected-oracle pilots have 8 and 30.
> Prospective main remains `NOT_READY` with zero eligible episodes. See the
> [current overview](../README.md) and [next actions](NEXT_READY_ACTIONS_20261008.md).

**Updated:** 2026-10-02
**Scientific data at the time of this snapshot:** none yet. Existing smoke traces were excluded.

## Architecture proposed at the time

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

The earlier `experiments.run_rag_factorial_nightly` plan called for:

1. Ollama/model preflight;
2. 80-target catalog validation;
3. retrieval-corpus coverage and leakage checks;
4. Docker image mapping and complete runtime safety suite;
5. one excluded provider/Docker smoke;
6. a 24-arm pilot: 3 families × 4 target cells × RAG on/off;
7. pilot log/receipt/infrastructure integrity gate;
8. main only if its old explicit flag and every prior gate had passed. This
   historical condition does not authorize prospective v1 collection.

Any failure stops the pipeline. The launcher never weakens the sandbox or silently
relabels infrastructure failure as agent failure.

## Commands

Static validation only:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_rag_factorial
```

The old pilot/main launcher commands are intentionally omitted: this document
does not authorize collection under the current prospective protocol. Consult
the [12-gate matrix](MAIN_RELEASE_GATE_MATRIX_20261005.md) before designing a
new release.

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

Raw trajectories and generated result files were Git-ignored at the time of
this historical plan. The present local branch tracks them; their immutable
receipts still need to be preserved, and remote availability must be checked
separately after push.
