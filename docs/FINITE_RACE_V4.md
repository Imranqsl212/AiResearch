# Finite counter-race benchmark v4 — offline engineering fixture

This separate controlled fixture models **one** concurrency mechanism: a lost update when two acknowledged increments race. It does not execute candidate source code, reproduce a database engine, or establish general race-condition security. It is connected to the excluded R0 pilot collector, and no v4 episode is eligible for the main study.

## Bounded contract

A candidate chooses `update ∈ {read_write, atomic_add}` and `lock ∈ {none, request_mutex, worker_mutex}`. The only workload is two increments, A and B, starting from count 0. Security requires both requests to be acknowledged and the final count to equal 2 **for every permitted schedule**. `read_write` has a read and a write per request. The exhaustive oracle explores all six order-preserving interleavings when no shared lock serializes the two requests, and both serial orders when both requests share a worker mutex. `atomic_add` is a single-step operation per request if the backend supports it; otherwise it returns an error and cannot meet the availability part of the contract.

The weak test executes A then B serially. It accepts the unguarded read/write policy even though an interleaving in which both requests read 0 ends at count 1. The strong evaluator uses a separate rule-based implementation; [`finite_race_reference_v4.py`](../benchmark/finite_race_reference_v4.py) uses its own explicit-state search and compares the full weak, strong, security-oracle and gate receipt on every candidate in every cell. Both checkers share the declared worker assignment and atomic-capability facts. Agreement detects implementation errors within this model; it is not an independent measurement of real storage behavior.

## Five matched cells

| Cell | Evaluator-owned environment | Derived truth | Feedback after failure |
| --- | --- | --- | --- |
| C1 | One worker; atomic supported | Repairable | Generic |
| C2 | One worker; atomic supported | Repairable | A concrete failed schedule or unsupported-operation diagnostic |
| C3 | Two workers; atomic unsupported | Unrepairable in the six-policy grammar | Generic |
| C4 | Two workers; atomic unsupported | Unrepairable in the six-policy grammar | The checked environment and a counterexample for every policy |
| C5 | One worker; atomic supported; reject-secure gate | Evaluator mismatch | Generic failure even for an oracle-secure policy |

The agent-facing projection, starter policy, tools, and budgets are byte-identical across cells. The hidden worker assignment, backend capability, condition label, proofs, and gate mode are not in that projection. Unrepairability is **derived by enumerating all six allowed policies**, not from the condition label. With two workers, request-local and worker-local mutexes cannot coordinate both writes; with atomic support absent, neither atomic policy acknowledges the requests. A real system could add a distributed lock, change the data store, or alter the architecture. Those actions are intentionally outside this finite grammar, so the C3/C4 claim does not extend to unrestricted code repair.

The C5 benchmark gate rejects a policy that the strong test and finite security oracle accept. This is an injected calibration mismatch, not an estimate of how often real evaluators make false rejections. The C1 secure worker-mutex and atomic policies have two distinct insecure mutations: replacing the worker mutex with a request-local mutex and replacing atomic addition with unguarded read/write. The weak sequential test misses both; the strong finite evaluator detects both. Two mutations are far too few for a general sensitivity claim.

## Artifacts and verification

[`benchmark/tasks/v4_race`](../benchmark/tasks/v4_race) contains five task JSON files, five proof JSON files, evaluator-only reference and mutation policies, and a SHA-256 file index. [`generate_finite_race_v4.py`](../benchmark/generate_finite_race_v4.py) regenerates this set; [`validate_finite_race_v4.py`](../benchmark/validate_finite_race_v4.py) rejects altered or unindexed files, checks public parity and proofs, and performs all **30** candidate-condition comparisons against the separate state-machine checker. [`test_finite_race_v4.py`](../tests/test_finite_race_v4.py) includes tamper, mutation, mismatch and counterexample checks.

Run:

```sh
python3 -m benchmark.validate_finite_race_v4
PYTHONPATH=. python3 tests/test_finite_race_v4.py
```

Passing these checks makes v4 a bounded finite research fixture. The collector and strict JSON adapter now accept its public two-field candidate shape in R0 pilots; the main phase remains blocked. A prescheduled five-slot qwen3:4b pilot is reported in [COUNTER_RACE_V4_LIVE_PILOT_20261004.md](COUNTER_RACE_V4_LIVE_PILOT_20261004.md). Admission to a prospective main cohort still needs an independent scientific review of the threat model and condition parity, prespecified mutations, broader model replication, and stronger external-validity evidence. The root READY status remains unchanged.
