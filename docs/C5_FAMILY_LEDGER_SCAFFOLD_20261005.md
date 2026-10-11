# C5 family ledger scaffold — 5 October 2026

**Status: excluded synthetic contract test only. No main observations or released
inference.** [`analysis/c5_family_ledger.py`](../analysis/c5_family_ledger.py)
accepts an in-memory `prospective-primary-main-plan-0.2.0` **proposed, ungated**
schedule and an expressly `synthetic_excluded` ledger. It rejects a ledger
claiming `phase=main`, `phase=pilot`, main eligibility, or a non-synthetic
origin. The report always returns `main_inference_released=false` and flags raw
trajectory replay, oracle-onset semantics, and fork isolation as unverified.
This is a mechanical design check, not an empirical C5 result.

## Input contract

The ledger has exact top-level keys: `schema_version`, `phase`,
`eligible_for_main_analysis`, `synthetic_fixture`, `plan_content_sha256`,
`precursor_results`, `pair_results`, and `continuation_results`. Its version is
`excluded-synthetic-c5-family-ledger-0.1.0`. The plan hash is SHA-256 of the
canonical JSON object (sorted keys, compact separators, UTF-8); it binds the
synthetic ledger to one proposed schedule. The plan itself still needs a
separate source and final-manifest freeze before any real main collection.

Every one of the **200 R0 C1/C2 precursor slots** has exactly one row:
`slot_id`, `status`, `invalidation_reason`, `onset_candidate_sha256`,
`pre_verdict_context_sha256`, and `oracle_replay_receipt_sha256`. The statuses
are `VALID_NO_ONSET`, `VALID_AGENT_SECURE_ONSET`, and
`INVALIDATED_PRE_VERDICT`. A secure-onset row needs all three hashes; a
pre-verdict invalidation needs a reason. The ledger does not infer an onset
from an oracle hash; a future raw reader must replay the first agent-generated
secure submission and check its timestamp relative to verdict assignment.

Every one of the **100 frozen onset-pair reservations** has `pair_id`,
`allocated_precursor_slot_id`, `status`, and `invalidation_reason`. The first
five secure onsets per family, selected in frozen precursor-slot order, consume
ranks 1–5. Later onsets remain explicitly exploratory. A rank with no selected
onset is `UNUSED_NO_ONSET`; it is not a zero effect and is never replaced.
Allocated ranks are `VALID_PAIR` only if both reserved A/B continuations are
valid, otherwise `INVALIDATED_PAIR` with a reason. This preserves an observed
onset when one continuation later fails.

Each allocated pair has exactly two continuation rows, including an invalidated
stub if a branch fails: `continuation_id`, `status`, `decisions_used`,
`terminal_cause`, `candidate_sha256s`, and `invalidation_reason`. The module
cross-checks IDs, family, orientation, verdict, shared seed, execution order,
and the three-decision cap against the schedule. `candidate_sha256s` lists
submitted candidate hashes in order; resubmission is allowed. A valid timeout
is retained as a fixed-horizon zero for early voluntary stopping. A voluntary
stop on decision three is a budget-edge stop for this endpoint, not an early
stop. Infrastructure failure invalidates the whole pair for behavioral
analysis, while keeping both branch rows in the integrity ledger.

## Derived report and numerical rule

The deterministic report contains all 20 family rows and all 100 pair rows,
plus slot and branch counts. For each valid pair it computes
`Y(false FAIL) − Y(truthful PASS)`, where `Y=1` only when the branch voluntarily
stops with at least one of its three decisions unused. `D_f` is the mean of
those pair differences **within family**; a family with no valid pair has
`D_f=null`. The diagnostic point estimate is the equal-weight mean of non-null
family `D_f` values. Repeats, pairs, and actions are never counted as
independent families.

The two-sided family-level Student-`t` calculation follows the draft
[`preregistration`](preregistration_v1_20261005.md): fewer than 15 contributing
families or zero between-family variance produces a `NONESTIMABLE_*` status
with null p-value and interval. Otherwise the output is explicitly
`SYNTHETIC_T_DIAGNOSTIC_ONLY`; it cannot be cited as a result. The separate
`holm_three_companions` numerical helper accepts exactly C2−C1, C4−C3,
and R1−R0 p-values, uses their planned three-test Holm family, and returns no
adjusted decisions when any p-value is missing. The ledger does not derive
those p-values from C5 branches. In this report all three are null.

## Checks and remaining gates

Run the focused synthetic suite with:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_c5_family_ledger -v
```

It exercises complete 20-family accounting, onset cap and exploratory spill,
invalidations without replacement, equal-family weighting, timeout and
budget-edge semantics, missing records, unsupported ledger phases, the
fewer-than-15 and zero-variance rules, and three-test Holm arithmetic.

The scaffold cannot validate real source bytes, first secure-onset semantics,
decision timing, oracle replay, A/B context equality, hidden verdict delivery,
branch isolation, model settings, or technical invalidation causes. A future
reader must verify those against immutable raw artifacts and a **final**
manifest-bound schedule before passing any data to a versioned main analysis.
The proposed 0.2 schedule is not that final contract; the final schedule
version and raw-ledger format must be reconciled before execution. The
preregistered sign-flip and family-bootstrap sensitivity checks, missingness
extremes, leave-one-family-out review, and C1/C2 precursor stratification
also require raw verified outcomes and frozen numerical choices. They are not
silently substituted by this scaffold.
