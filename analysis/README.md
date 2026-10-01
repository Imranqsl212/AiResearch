# Reproducible Analysis Pipeline

> **Crypto-scope status:** the existing implementation is a provenance-safe
> precollection scaffold from the generic stopping study. It has no eligible crypto
> trajectories and must be extended for the RD/UD/RW/UW crypto outcome fields before
> main analysis. Do not interpret its zero-data reports or old synthetic fixtures as
> crypto results.

This directory contains the read-only analysis pipeline for *When to Stop*.
It never writes under `experiments/runs/` or `experiments/manifests/`.

## Commands

Audit what is present without selecting data for inference:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m analysis.pipeline audit
```

`audit` writes zero-data derived outputs only when no main candidate needs an analysis lock. It refuses to overwrite a previously locked analysis or replace candidate main data with an empty report.

After a real, frozen main experiment exists, create an immutable input lock:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m analysis.pipeline freeze \
  --manifest experiments/manifests/EXPERIMENT.json \
  --lock analysis/locks/EXPERIMENT.json
```

Generate all derived tables, reports, and figures from that exact lock:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m analysis.pipeline analyze \
  --lock analysis/locks/EXPERIMENT.json
```

`freeze` uses exclusive creation and records SHA-256 hashes for the manifest,
pre-run schedule, finalized all-attempt ledger, **every** raw log/receipt
(including setup retries and infrastructure controls), all scheduled task
definitions, optional annotation file, and analysis code. `analyze` rebuilds
the entire raw population and verifies it before producing a number. A fixture,
missing/invalid Git revision, malformed receipt, unlisted raw attempt, or
ledger/schedule mismatch is a hard stop. A fully missing sample may be locked
for audit, but never produces a behavioral estimate.

The schedule has one slot per task × repeat, blocked by task family and repeat
with a frozen seed. A slot can have at most two retries, exclusively after
pre-handoff infrastructure failures. `TASK_HANDOFF_START` is logged before the
adapter receives the task; an abort after handoff start is the selected outcome
for its slot and cannot be rerun. Missing slots require an explicit reason;
they are never imputed as failure or success. Infrastructure-control slots are
accounted for but excluded from the main behavioral sample. Main tasks still
require a frozen index-action/evidence contract and UD exact stopping allowlist.
The metadata-only ledger writer has synthetic tests and emits a lock-compatible
all-slot ledger, but it is not connected to real collection. A real main schedule,
provider orchestration, and durable raw archive remain **NOT IMPLEMENTED**.

The derived `schedule_status.csv`, `attempt_ledger.csv`, and
`infrastructure_status.csv` expose denominators, exclusions, and retry counts.
Post-action infrastructure aborts remain visible in the run-level table but
are excluded from behavioral summaries. More than 5% missing, infrastructure,
or unknown main slots pauses confirmatory interpretation.
H1 positive recovery and H2 require evaluator-origin per-action goal receipts.
The in-memory fixture runner now emits these and the main input lock requires
one for every completed action in a non-aborted run. This is only a wiring
check: no independently reviewed executable-task action verifier or eligible
agent run exists. Confirmatory GEE/model-first tests are NOT IMPLEMENTED;
available paired permutation p-values are explicitly
exploratory and cannot establish preregistered hypotheses.

An integrity-valid budget/timeout after index exposure remains in the H1
denominator. The independent *task-state* receipt determines observed RD
non-recovery or, with ordered action evidence, recovery; the forced *stop cause*
stays distinct. Verifier-confirmed terminal goal also counts toward descriptive
task success even if the stop cause was forced. A UD forced stop is not an agent's justified stop. Missing
or `UNKNOWN` task-state evidence is not converted into a behavioral zero.
`h1_component_summary.csv` reports RD and UD on their own observed families;
`calibration_pair_scores.csv` and its CPS summary require complete pairs.
`h1_lower_bound_sensitivity.csv` separately zero-fills absent exposed cells
in all planned paired families. None runs the preregistered GEE test.

## Outputs

- `analysis/results.md` and `analysis/statistical_report.md` are generated,
  not hand-authored results.
- `tables/stopping_experiment/` contains input inventory, run-level metrics,
  scheduled-slot and all-attempt ledgers, infrastructure status, cluster
  summaries, comparison output, and representative-trajectory selection.
- `figures/stopping_experiment/` contains only data-backed SVG figures and a
  figure manifest. If no eligible data exists, it deliberately creates no
  chart that could be mistaken for a result.

See [codebook.md](codebook.md) for definitions, denominators, and the boundary
between surface action changes and strategy transitions.

Precollection H1 sample-size sensitivity is separately documented in
[power_simulation.md](power_simulation.md). Its deterministic synthetic
studentized-family proxy is **not** the preregistered GEE test and cannot
clear the main-study power gate or supply an empirical agent result.
