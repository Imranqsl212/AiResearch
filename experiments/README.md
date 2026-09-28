# Experiment records

`experiments/` stores frozen configuration manifests and evaluator-owned observable
trajectory records. It is not a result directory for the main study: no provider-backed
agent run has been launched.

- `manifests/` contains immutable JSON configuration records.
- `runs/` contains append-only JSONL event streams and one final receipt per run.
- `schemas/` defines their machine-readable interchange contracts.
- `run_e2e_fixture.py` runs one deterministic in-memory integration smoke fixture.
- `validate_artifacts.py` verifies an existing manifest/log/receipt triplet without
  executing an agent or task.

The smoke fixture is intentionally excluded from any scientific analysis. It verifies
only that `Benchmark → Adapter → local finite-state sandbox → independent verifier →
trajectory logger` is connected. It has no model provider, credentials, Docker
container, external target, or network capability.

Run it once from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m experiments.run_e2e_fixture --json
```

Run artifacts are append-only. Reusing a run ID would overwrite neither the JSONL log
nor its receipt; choose a new run ID for another smoke invocation. A reused experiment
ID is accepted only if its immutable manifest configuration is identical.
