# Proposed main C5 allocation: excluded structural dry-run

**This is a synthetic planning check, not an experiment.** The proposed
one-model schedule contains 600 full C1–C4/R0 and C1–C2/R1 episodes, 100
conditional C5 pair reservations and 200 branch IDs. The
[`dry-run-c5-allocation`](../experiments/main_orchestrator.py) path checked
allocation accounting without a model call or semantic onset validation.
Its synthetic model name and digest are placeholders; the plan remains
`PROPOSED_MAIN_UNGATED`, and the main collector is still disabled.

The [saved input plan](../experiments/runs/main_c5_structural_dry_run_20261005_v2/plan.json)
and [synthetic precursor ledger](../experiments/runs/main_c5_structural_dry_run_20261005_v2/precursor_ledger.json)
cover all 200 R0 C1/C2 precursor slots. The ledger deliberately assigns nine
simulated secure onsets, one simulated **pre-verdict** invalidation and 190
simulated nononsets. It says nothing about failures after an onset has already
been captured; such a later branch failure must remain attached to that pair.
Six onsets occur in one family, two in another and one in a third. The frozen
first-five-per-family rule allocates eight pairs and 16 continuation IDs;
the sixth onset is retained as exploratory overflow. Ninety-two reserved
pairs remain unused. The [write-once report](../experiments/runs/main_c5_structural_dry_run_20261005_v2/c5_dry_run.json)
records every precursor, pair and family disposition.

| Saved file | SHA-256 |
| --- | --- |
| `plan.json` | `bd2f98e9ca138ca3ad5893a088054b83ec9d5d2aa7f4bf4e2be97fd93b164df8` |
| `precursor_ledger.json` | `a30b5dd61ed2fcdf0a6bcb59425ec1aeeced5898f117482d66cfbbe4e5cd0b2e` |
| `c5_dry_run.json` | `8fe44c1c21bace0b3977890b016ec194eec1e99e58161f93e19f228b455eac6a` |

The CLI and tests reject missing, duplicated, foreign or observed-status ledger
rows, changed plan bytes and output overwrite. This v2 report supersedes an
earlier local structural trial made before the pre-verdict invalidation label
was clarified; that earlier write-once trial remains untouched. This verifies reservation
accounting only. A main implementation still needs independent family and R1
admission, exact live source/runtime binding, agent-generated oracle-secure
onset validation, two matched provider continuations, saved requests, retained
invalidations and the full release gate. The local raw directory is Git
ignored and its hashes are not third-party timestamps.
