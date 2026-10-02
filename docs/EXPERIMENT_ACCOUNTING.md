# Experiment accounting and cohort boundaries

The local accounting script scans every existing experiment manifest, run log,
receipt, result JSONL file, and nightly report. It records identifiers,
SHA-256 hashes, validator status, and the source files linking a result to a
run. It does not read private model reasoning or edit earlier data.

Before the v2 launch, the snapshot found 36 prior runs: 24 excluded smokes,
11 pilot runs, and one engineering fixture. Outcomes were 14 verifier successes,
9 verifier non-successes, and 13 infrastructure aborts. The current artifact
validator passed 24 of the 36 historical records. Twelve older records have
legacy verifier-event discrepancies or incomplete infrastructure-abort events.
Those records remain indexed with the exact validation errors; they are not
silently counted as valid results.

The prior `rag-factorial` pilot has three run logs, two completed result rows,
and one manually interrupted run. The `rag-overnight-v1` pilot has eight result
rows, including one Ollama request timeout. Its nightly report is
`PILOT_GATE_FAILED`, so that profile has no main observations.

The v2 profile uses a new experiment identifier and repeats its eight-arm
pilot under a frozen 600-second Ollama request timeout. All prior runs are
engineering history or pilot evidence. Only the separately scheduled v2 main
arms belong to the new exploratory main cohort. One run per arm cannot support
confirmatory GEE or a claim about population-level RAG benefit.

To regenerate a read-only summary or create a local snapshot:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.accounting
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.accounting --write
```

Snapshots are saved under `experiments/reports/` and excluded from public Git
until the underlying raw data and release policy are reviewed.
