# Reproduction and release boundary

## Current result

The repository contains a completed **legacy exploratory** study and an unfinished prospective v1 design. No v1 main empirical result exists. The tracked historical raw trajectories, indexes, and receipts let a complete checkout independently rerun the 40-episode analysis; a partial export cannot. Do not substitute the derived tables for raw evidence. Git availability does not certify privacy review or journal supplementary release.

## Reproduce the legacy exploratory analysis

For a quick read-only check from the repository root, run:

```sh
python3 -B -m reproduction.verify_project
```

It rebuilds the historical paper summary in a temporary directory, compares
that JSON with the tracked result, independently recounts the terminal
test–gate disagreement from the transformed archive, and checks the source
fidelity report. A successful run prints `VERIFIED_EXPLORATORY_EVIDENCE`,
including 40 main episodes, 25 raw finite-test passes, 16 accepted finals,
and 9/20 disagreements in the nominally unavailable arm. It uses the saved
artifacts and Python standard library; it does not call the model, execute
candidate code, approve a data release, or open the prospective main gate.

With the tracked `experiments/runs/` and `experiments/raw_archive/` present:

```sh
python3 -B -m analysis.paper_pipeline --output paper/artifacts
```

The pipeline validates the old indexed main and pilot inputs, checks local hashes, and writes derived tables. It does not execute model-generated code or relabel the old `UD/UW` arms as truly impossible. A checkout missing the raw files cannot complete this step; consult [paper/README.md](../paper/README.md) for the exact legacy provenance and renderer.

## Validate prospective controlled engineering artifacts

The repository root [experiment_manifest.json](../experiment_manifest.json) deliberately has `status: NOT_READY` and null freeze fields. It is a template, not a fabricated experiment lock. A main-run preflight must refuse that manifest and require real proof artifacts, evaluator/security-oracle agreement tests, an exact model/runtime freeze, complete logs, and a clean source revision.

Run [reproduce.sh](reproduce.sh) from this workspace to check the 20 authored
finite families, retrieval and baseline units, evaluator calibration, the v1
analysis status, and the static main preflight. The families have 100 C1–C5
task/proof rows and 1,820 recorded finite candidate/condition checks across
the four original mechanisms and three later batches. It also checks the
separate, unadmitted batch-C v7 and R1 v0.2 candidates and excluded main-path
scaffolds. The script's offline unit/integration suite, six focused real-code regressions, and fixture
validators need no ignored model pilot logs, Docker run, or Ollama call. The
R1 v0.2 source-review validator requires the tracked
[22-page source snapshot archive](../docs/R1_V2_PRIVATE_SOURCE_SNAPSHOTS_20261005.md)
in this repository. A partial export without it cannot run the same
full validation. Use a **full-history Git checkout** for this broader script:
two excluded-pilot audits verify their frozen source commit, so a shallow
clone is insufficient. Their archived absolute paths are mapped to the
current checkout while retaining the original records and file-hash checks.
One Stripe page in that archive is a documented redacted
release copy; its exact original bytes remain local, as recorded in the
[redaction audit](../docs/R1_V2_PUBLICATION_REDACTION_20261012.md). It prints
`NO_ELIGIBLE_DATA` and `NOT_READY` for the current design-stage repository.
These are successful **integrity checks of an incomplete study**, not agent
results or independent human task admission.

For a future checked-in freeze, `experiment.git_sha` identifies the clean **source commit before the freeze file is finalized**. The next freeze commit may change only `experiment_manifest.json`; preflight compares its current bytes with the tracked freeze blob, verifies all artifact digests, and requires a clean tree. This two-commit scheme avoids placing a commit hash inside the same commit that it names. A fresh runtime safety receipt and completed pilot remain separate live gates.

Only an excluded engineering or pilot run may be used to test the new collection path before that gate passes. Such runs must carry `phase: engineering` or `phase: pilot` and cannot appear in main result tables. The analysis must return `NO_ELIGIBLE_DATA` until a valid v1 main cohort exists.

The local scripted wiring pilot can be reconstructed with `python3 -B -m experiments.run_v1_engineering_pilot --output-dir experiments/runs/<new-name>`. It creates 15 **scripted, non-agent** episodes covering five conditions and R0/R1/R2, refuses an existing output directory, and saves a prespecified engineering schedule and retrieval manifest. Run it a second time under another new directory, then use `python3 -B -m reproduction.compare_v1_pilots <first-dir> <second-dir>` to compare deterministic fields after each episode's hashes and proofs are revalidated. The two local runs on 3 October 2026 matched all 15 deterministic traces; timestamps and latencies are intentionally excluded. Their saved raw files are tracked in this branch, but this replay is not a model replication or a passed main-run gate.

New engineering episode manifests also record whether the source tree was dirty and SHA-256 digests of the evaluator, retrieval, collector, adapter, and contract files. A Git commit by itself does not identify an uncommitted engineering implementation. These digests improve local traceability but do not replace a clean committed main freeze.

The newer [private excluded-pilot bundle](../docs/PRIVATE_EXCLUDED_PILOT_BUNDLE_20261005.md)
preserves raw records for the 40-slot full-catalog, 14-pair C5, and 40-slot
R1 C2 pilots. Run
`python3 -B -m analysis.build_private_excluded_pilot_bundle verify` in the
original workspace to recheck its member hashes and
descriptive counts without a model call. It is tracked in this branch, contains raw
local paths and provider text, and has no recorded independent privacy/content review.
Its verification is separate from the legacy paper and prospective main study.

`experiments.run_v1_live_pilot` is a separate, **excluded** single-episode Ollama smoke path. Earlier local `qwen3:4b` C4 checks exposed unstructured-prose capture and a no-action response mislabeled as voluntary stopping. The first two traces have invalidation sidecars; the third correctly records `ERROR` and `AGENT_PROTOCOL_NO_ACTION`. A later [strict JSON-action pilot](../docs/V1_LIVE_JSON_PROTOCOL_PILOT.md) produced one valid live `INSPECT` after the public C4 witness, then stopped because its deliberately limited action budget was exhausted. Subsequent [C1 trajectory checks](../docs/V1_LIVE_C1_TRAJECTORY_PILOT.md) captured `INSPECT`, `SUBMIT`, and `TERMINATE`: the submitted policy remained insecure, and the voluntary termination used the last available action. An initial C1 invocation without loopback access was retained as an invalidated infrastructure abort. These pilots demonstrate structured-action capture and separate stop causes; they do not establish repair or appropriate stopping. All remain excluded from main inference.

A later [five-condition live block](../docs/V1_IMMEDIATE_LIVE_PILOT_20261003.md) ran one C1–C5/R0 `qwen3:4b` episode per prescheduled slot. All five logs, proofs, and hashes validate with `python3 -B -m analysis.summarize_v1_live_pilot --manifest-dir experiments/runs/v1-live-r0-c1-c5-20261003` in this workspace. C2 contained one finite-oracle-secure gate pass; C4 ended voluntarily after the starter proof with one action remaining, following two insecure submissions. The raw block is tracked in this branch. The report is descriptive pilot evidence, not a main result or a causal estimate.

For privacy and construct validity, a contract-valid finite decision table is stored in full; malformed tool arguments are retained as a hash plus an invalid-action marker. Arbitrary malformed text and provider-native reasoning are not scientific source artifacts. This means strategy annotation must mark that transition unassessable rather than reconstruct code that was never safely retained.

## Required release bundle for an independent researcher

1. The frozen source commit and dependency/runtime versions, plus prompt/tool schema and model snapshot or weights digest.
2. Task manifests and individually checked feasibility proof artifacts; constructively valid repair references; mutation suite and weak/strong/oracle receipts.
3. Corpus files, per-document hashes, retrieval algorithm/configuration and every episode's retrieval exposure record.
4. A pre-run randomized schedule, all-slot attempt ledger, raw per-action JSONL, candidate artifacts, evaluator receipts, stop classifications, and invalidation reasons.
5. The read-only deterministic analysis code, generated data tables/figures, and a manifest that links each paper number back to raw input hashes.

Independent privacy and code-release review of old and future raw traces has not been recorded. Local hash seals establish consistency after capture, not approval for journal reuse or tamper-proof provenance.
