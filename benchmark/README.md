# Cryptographic repair benchmark

## Current finite stopping-study catalog

The newer stopping-study pilot has **20 authored finite families** with one
C1–C5 task per family (100 task cells). Their indexes are in `tasks/v1/`,
`tasks/v2_path/`, `tasks/v3_replay/`, `tasks/v4_race/`, `tasks/v5_batch_a/`,
`tasks/v5_batch_b/`, and `tasks/v6_batch_c/`. Run the machine pre-review with
`python3 -B -m analysis.admission_review`; it currently reports `CONDITIONAL`
because independent human admission review is missing. The batch-C precheck is
`python3 -B -m benchmark.validate_finite_batch_c_v6`. Its exact coverage and
remaining construct concerns are recorded in
[`docs/benchmark_admission_precheck_20261004.md`](../docs/benchmark_admission_precheck_20261004.md).

These finite policies are data structures, not executable security repairs.
The SQLite and shell-injection real-code fixtures are separate calibration
examples and are not main-study agent episodes.

## Earlier four-cell cryptographic development suite

This section documents the earlier local benchmark for *When Secure-Code Repair
Fails: how an AI agent responds to cryptographic misuse feedback*. It is a safe,
offline repair benchmark—not a penetration-testing framework and not a live target.

That development suite is `benchmark/tasks/four_cell/`, version `0.3.0`. It contains three
matched crypto families (`aead`, `nonce`, `key-management`), each with four cells:

- `RD`: repairable, diagnostic feedback;
- `UD`: securely unavailable, diagnostic feedback;
- `RW`: repairable, weak but truthful feedback;
- `UW`: securely unavailable, weak but truthful feedback.

Run the static quality gate without launching an agent:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m benchmark.quality_four_cell --json
```

The gate checks schema shape, family balance, deterministic reference behavior,
crypto-specific invariants, and independent receipt semantics. It does not authorize
provider calls or an experiment. Runtime safety, executable target validation, and
agent integration are separate gates.

Key paths:

- `schemas/four_cell_task.schema.json` — active versioned task contract;
- `schemas/trajectory.schema.json` — observable trajectory contract;
- `tasks/four_cell/` — active 12-task development suite;
- `validators/` — evaluator-owned receipts and oracle checks;
- `four_cell.py` — deterministic task generator;
- `quality_four_cell.py` — static quality gate.

The agent-visible projection must contain only the opaque task card, bounded crypto
tool contract, and resource limits. Conditions, reference plans, verifier code,
hidden state, credentials, and host paths stay evaluator-only.

`tasks/legacy_four_cell_general/` and `tasks/pilot/` are retained for audit history.
They are not part of the active crypto benchmark or any future denominator.
