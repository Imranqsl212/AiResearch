# Finite fixture evaluator calibration — 4 October 2026

This is exhaustive calibration over four authored finite candidate languages. The rows are candidate/condition decisions, not independent real-code security observations.
All saved proofs and every result were checked against separate reference implementations.

| Family | Candidate/condition checks | Weak raw false accepts | Gate false rejects | C1 insecure mutations caught by raw / gate |
| --- | ---: | ---: | ---: | ---: |
| authorization | 40 | 2 | 1 | 2/2 / 2/2 |
| path-boundary | 1280 | 2 | 1 | 2/2 / 2/2 |
| transaction_replay | 80 | 37 | 1 | 0/2 / 2/2 |
| counter_race | 30 | 12 | 4 | 0/2 / 2/2 |

Total: **20** verified proofs and **1430** candidate/condition checks. The weak replay test checks only the first request and misses both saved C1 replay mutations; the weak race test runs requests serially and misses both saved C1 race mutations. Each gate false rejection comes from a deliberately designed C5 gate. The stronger gate is itself part of the authored finite fixture; these counts are not a measured population error rate for real software.

The full machine-readable confusion matrices, mutation IDs, and input hashes are in [finite_fixture_calibration_20261004.json](../analysis/finite_fixture_calibration_20261004.json).
