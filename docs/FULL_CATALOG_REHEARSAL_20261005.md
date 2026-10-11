# Full finite-catalog orchestration rehearsal — 5 October 2026

## Scope

This was an **excluded scripted integration run**, not a model experiment or a main-study cohort. The frozen schedule covered all 20 authored finite families, each with C1–C5 once, in R0 only: 100 prescheduled slots. A scripted adapter either submitted a saved satisfying candidate or terminated. No Ollama request, candidate source execution, or scientific rate was produced.

The saved output is `experiments/runs/full_catalog_rehearsal_20261005` (Git ignored). Its plan records seven task-index paths and binds every referenced task/proof hash, implementation source hashes, the root draft manifest, one scripted-model identity, and the seeded slot order. Its pre-run source archive and preflight bind the seven index files byte for byte. A later planner revision also puts index hashes directly in newly created plans; that change does not retroactively alter this saved run. Every slot was reserved once; no replacement was allowed.

## Result

`run-rehearsal` reported **100/100 valid excluded slots, 0 invalidations, 0 replacements, 0 main-eligible episodes**. `verify-rehearsal` returned `VERIFIED_EXCLUDED_REHEARSAL` with `current_source_matches_pre_run_archive=true` at verification time and analysis status `NO_ELIGIBLE_DATA`. The saved `run.receipt.json` file SHA-256 reported by verification was `0075d2590071e7eccdd7b91d215fabf7976d49d27a7b3e1962b64acf676d8e38`.

This closes one plumbing gap: the v1 collector now accepts the public candidate options and modes of batch A/B/C, records R0 queries for domains absent from the v1 corpus, and exposes the batch-C tool contract without revealing hidden condition labels or oracle facts. A separate test exercises one secure C1 submission in each of the 20 families.

## Limits and next gates

- All 100 trajectories are scripted and excluded. They do not estimate model behavior, security correctness outside the authored finite spaces, or any causal effect.
- RAG R1/R2 remains supported only for the original authorization family in this collector. The frozen v1/v2 retrieval corpora do not cover all 20 newly authored finite domains. A new reviewed corpus or a preregistered RAG subset is required.
- Independent human admission is missing. Batch C's schematic impossibility witness and finite nonce semantics need expert review. This rehearsal cannot clear those scientific gates.
- The main collector still refuses `phase=main`; the root manifest is draft. A model-backed, exact-source rehearsal under a final approved plan and a complete live preflight remain necessary.

## Reproduction

Run with a new output directory; the existing directory is intentionally create-once:

```sh
python3 -B -m experiments.main_orchestrator prepare-rehearsal \
  --output-dir experiments/runs/a-new-full-catalog-rehearsal --all-families-r0
python3 -B -m experiments.main_orchestrator run-rehearsal \
  --output-dir experiments/runs/a-new-full-catalog-rehearsal
python3 -B -m experiments.main_orchestrator verify-rehearsal \
  --output-dir experiments/runs/a-new-full-catalog-rehearsal
```
