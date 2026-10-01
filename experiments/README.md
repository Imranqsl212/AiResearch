# Experiment records

`experiments/` stores frozen configuration manifests and evaluator-owned observable
trajectory records. It is not a result directory for the main study: no provider-backed
agent run has been launched.

- `manifests/` contains immutable JSON configuration records.
- `schedules/` is the pre-run deterministic family/repeat-blocked slot plan.
- `ledgers/` is the finalized all-attempt record, including missing slots and
  at most two setup retries per slot.
- `attempt_journal/` stores create-once reservations and validated completions;
- `raw_archive.py` copies completed observable logs once, seals their hashes, and
  rejects later content replacement;
  pending reservations are retained across restart and block new attempts.
- `runs/` contains append-only JSONL event streams and one final receipt per run.
- `schemas/` defines their machine-readable interchange contracts.
- `run_e2e_fixture.py` runs one deterministic in-memory integration smoke fixture.
- `validate_artifacts.py` verifies an existing manifest/log/receipt triplet without
  executing an agent or task.
- `attempt_ledger.py` is a metadata-only journal writer. It never runs an agent,
  starts Docker, opens the network, or grants permission to collect data.

The smoke fixture is intentionally excluded from any scientific analysis. It verifies
only that `Benchmark → Adapter → local finite-state sandbox → independent verifier →
trajectory logger` is connected. It has no model provider, credentials, Docker
container, external target, or network capability.

Run the current v0.1.4 fixture into a fresh disposable directory from the repository root:

```sh
fixture_output_dir=$(mktemp -d)
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.run_e2e_fixture \
  --output-root "$fixture_output_dir" --json
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.validate_artifacts \
  --manifest "$fixture_output_dir/manifests/e2e-local-finite-state-v0.1.4.json" \
  --log "$fixture_output_dir/runs/e2e-local-finite-state-v0.1.4/fixture-run-0001.jsonl" \
  --receipt "$fixture_output_dir/runs/e2e-local-finite-state-v0.1.4/fixture-run-0001.receipt.json" \
  --require-action-verifier --json
```

Run artifacts are append-only. Reusing a run ID would overwrite neither the JSONL log
nor its receipt; choose a new run ID for another smoke invocation. A reused experiment
ID is accepted only if its immutable manifest configuration is identical. The
historical tracked v0.1.2 fixture lacks per-action receipts and remains readable
without `--require-action-verifier`; it is not silently rewritten.

For a future main study, build the schedule with
[`build_schedule`](schedule.py), write it once with `write_schedule`, and put its
SHA-256 in the manifest's `schedule_sha256` before the first run. Schedule
conditions are `RD`, `UD`, `RW`, `UW`, and separate `INFRA_CONTROL`. The
confirmatory schedule validator now requires exactly one RD, UD, RW, and UW
task in each main task family; a partial or duplicate family is rejected
before an analysis input lock can be frozen. Infrastructure controls remain
outside these matched families. The
finalized ledger format is [`attempt_ledger.schema.json`](schemas/attempt_ledger.schema.json):
every slot is `RECORDED` with a selected run or `MISSING` with a declared
reason. All prior attempts must be pre-handoff infrastructure failures;
an abort after `TASK_HANDOFF_START`, `INITIAL_OBSERVATION`, or any action occupies the slot and may not
be retried. The analysis lock
rechecks these rules against every raw log and receipt and rejects unlisted
files. Non-aborted selected attempts also require one evaluator receipt per
completed action. The metadata writer is implemented and synthetic-tested, but
provider orchestration, durable crash recovery of incomplete raw attempts, physical
write-once storage, and a real frozen main schedule are **NOT IMPLEMENTED**. The local
archive is an integrity layer and must be copied to independently controlled storage
after sealing.
An unresolved reservation must be audited and resolved with a valid raw abort
record; it cannot be silently cancelled or retried. This engineering validation
is not a license to collect.

New manifests, schedules, journals, ledgers, and raw runs are Git-ignored by
default to avoid accidental publication of unreviewed episode data. The
historical tracked scripted fixture remains explicitly versioned. Any eventual
research data release needs a separate reviewed allowlist, provenance check,
and retention/access decision; Git ignore is not an immutable storage policy.
