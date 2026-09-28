# Reproducible Analysis Pipeline

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
logs, receipts, selected task definitions, optional annotation file, and the
analysis code. `analyze` verifies every hash before producing a result. A
fixture, a missing Git revision, a malformed receipt, or no selected runs is a
hard stop for inferential analysis.

## Outputs

- `analysis/results.md` and `analysis/statistical_report.md` are generated,
  not hand-authored results.
- `tables/stopping_experiment/` contains input inventory, run-level metrics,
  cluster summaries, comparison output, and representative-trajectory
  selection.
- `figures/stopping_experiment/` contains only data-backed SVG figures and a
  figure manifest. If no eligible data exists, it deliberately creates no
  chart that could be mistaken for a result.

See [codebook.md](codebook.md) for definitions, denominators, and the boundary
between surface action changes and strategy transitions.
