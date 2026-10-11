# Read-only audit of excluded live-dispatch slots — 5 October 2026

[`analysis/audit_excluded_live_dispatch_crash.py`](../analysis/audit_excluded_live_dispatch_crash.py)
inspects a write-once slot directory from
[`experiments/main_live_dispatch_excluded.py`](../experiments/main_live_dispatch_excluded.py).
It makes no provider calls and does not create, repair, retry, or replace a
slot. It prints a JSON report to standard output; the original directory is
untouched.

Run from the repository root:

```sh
python3 -B -m analysis.audit_excluded_live_dispatch_crash /absolute/path/to/slot
python3 -B -m unittest -v tests.test_excluded_live_dispatch_crash_audit
```

The command accepts multiple slot directories and returns one report per
directory. Exit status is 0 for a verified or incomplete directory and 1 if
any directory has malformed or contradictory artifacts. Callers must inspect
`classification` and `integrity`; exit 0 does **not** mean that an unfinished
slot is complete or usable. Every report sets `phase=pilot`,
`eligible_for_main_analysis=false`, `main_dispatch_allowed=false`,
`retry_allowed=false`, and `replacement_allowed=false`.

| Evidence at the end of an unreceipted slot | Classification | Send evidence |
| --- | --- | --- |
| Slot opened; no numbered request | `OPEN_NO_DISPATCH` | No start record |
| Request bytes, no dispatch-start | `PRE_DISPATCH_INCOMPLETE` | No start record |
| Dispatch-start, no response or return | `DISPATCH_OUTCOME_UNKNOWN` | **Unknown after start** |
| Response bytes, no dispatch-return | `RESPONSE_WITHOUT_RETURN` | Response archived; no return record |
| Dispatch-return, no decision | `DECISION_PENDING` | Return recorded |
| Decision, no final receipt | `FINAL_RECEIPT_MISSING` | Return recorded |

An incomplete initialization is `INITIALIZATION_PARTIAL`. A verified final
receipt is `CLOSED_COMPLETED` or `CLOSED_INVALIDATED`; the former still means
`COMPLETED_EXCLUDED_UNVERIFIED`, never a main observation. Malformed JSON,
hash mismatches, impossible file order, symlinks, unknown files, or a final
receipt that cannot be verified produce `integrity=failed` with issue codes.
`failed` identifies unusable evidence; it does not distinguish a hard crash,
storage damage, later deletion, and tampering.

The audit checks canonical JSON records, the plan/open/inventory links,
archived source hashes, request and response hashes against start/return
records, request options, decision content, and sequence order. If a final
receipt exists, it also invokes the existing offline verifier. No result
permits resuming the directory or issuing the same slot again. A request file
without a start record reflects a pre-dispatch prefix **if the writer's files
remain intact**. A missing start record by itself cannot prove that a model
was never called. A start record without a return makes the send outcome
ambiguous even when the file was durably written before `send` in a normal
process run.

This is an inspection of a filesystem snapshot. It cannot establish whether
the process is still active, prove an `fsync` happened, establish a provider's
wire bytes or execution, authenticate the provider or timestamp, or detect
coordinated edits that leave all internal hashes consistent. It does not
provide an evaluator, independent oracle, main collector gate, or admission
to main analysis. Preserve and review the original private bytes separately.
