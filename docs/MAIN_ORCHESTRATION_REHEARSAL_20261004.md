# Prospective main orchestration: excluded rehearsal (4 October 2026)

## What was implemented

[`experiments/main_orchestrator.py`](../experiments/main_orchestrator.py) builds a seeded, deterministic condition × family × repetition × retrieval × model schedule before any agent call. Every slot binds an indexed task and independent proof hash, model digest, retrieval mode, episode seed, source-file hash set, root manifest hash and inference budget configuration. A proposed `main` design requires at least 20 complete C1–C5 families, five repetitions, R0/R1, and two actual models. The current twelve families cannot pass that design check; eight more and human admission review are still required.

The `main-gate` and `refuse-main` entry points call the static freeze checker and validate an optional prescheduled main plan. They fail closed because the checked-in manifest is a draft and `v1_collector` still rejects `phase="main"`. The gate records unimplemented live checks as false, including a fresh official safety suite, reviewed mutation evidence, exact request archiving, model freeze, annotation and statistics plans. It does not run a model, candidate, or Docker container on this failed path. The saved refusal is [`experiments/runs/main_refusal_20261004/main_refusal.json`](../experiments/runs/main_refusal_20261004/main_refusal.json) (Git ignored): exit code 2, `model_calls=0`, `candidate_runs=0`, `eligible_main_episodes=0`.

The separate rehearsal path uses the real v1 collector only with `phase="pilot"` and a scripted fixture adapter. It reserves each slot once before handoff, retains partial errors as invalidations, never replaces an attempted slot, and writes a hash-linked all-slot receipt. Its `run.started.json` marker blocks relaunch after interruption. The verifier rechecks the factorial plan against the pre-run source archive, raw episode manifests, event logs, slot hashes, receipt counts and the analysis exclusion gate. It separately reports whether the *current* source still matches the pre-run snapshot. Local hashes detect ordinary drift but are not an authenticated timestamp or an independently held archive.

## Observed rehearsal

The final saved rehearsal is [`experiments/runs/main_path_rehearsal_v3_20261004`](../experiments/runs/main_path_rehearsal_v3_20261004) (Git ignored). It used one authorization family, C1–C5 × R0/R1/R2, one scripted repeat: **15 scheduled slots, 15 valid excluded episodes, zero invalidations, zero replacements, zero main-eligible episodes**. The run receipt SHA-256 is `a4b037ae2830e0d1407960921154837b758ab30b8ada1fd33377c7ac980e7390`; `verify-rehearsal` returned `ARCHIVE_INTEGRITY_VERIFIED_SOURCE_DRIFT`: the pre-run archive, tasks, slots, receipt, and exclusion gate verify, while the current checkout is explicitly marked different. `analysis.v1_pipeline` returned `NO_ELIGIBLE_DATA`. This was a wiring check, with **no live model calls** and no behavioral estimate.

Earlier saved `main_path_rehearsal_20261004` and `main_path_rehearsal_v2_20261004` outputs were also excluded. Source changed after each while the orchestration checks and benchmark registry were being extended. Their raw files were retained and never rewritten. The v3 rehearsal includes durable pre-run source-archive verification for subsequent checkout changes.

Targeted tests: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_main_orchestrator -v` — **4/4 PASS**. They cover full-factorial deterministic scheduling, source/task hash drift, main refusal without dispatch, all-slot receipt verification, tamper rejection, and one retained invalidation without replacement.

## Remaining main gates

This module is **not a READY claim**. A main-capable collector and full request-body archive must be reviewed; eight or more distinct independently reviewed families and broader executable-code tasks remain missing. A frozen, manifest-bound schedule needs the approved models, context controls, task release, mutation corpus, power-informed analysis, two-annotator plan, and an exact fresh safety pass. Only a manifest-only freeze commit and a complete live pre-run receipt may allow eligible `main` episodes. The present `main` entry point will continue to refuse collection until those changes exist.

## Commands

```sh
python3 -m experiments.main_orchestrator main-gate
python3 -m experiments.main_orchestrator prepare-rehearsal --output-dir experiments/runs/a-new-rehearsal
python3 -m experiments.main_orchestrator run-rehearsal --output-dir experiments/runs/a-new-rehearsal
python3 -m experiments.main_orchestrator verify-rehearsal --output-dir experiments/runs/a-new-rehearsal
```

`main-gate` intentionally exits 2 while the project is `NOT_READY`. A rehearsal output directory must be new; rerunning a started directory is refused.
