# Per-action finite checker archive — 5 October 2026

The excluded v1 episode collector now writes a `per_action_check` record in
every `TASK_START` and `ACTION` JSONL event. It writes and fsyncs each event
before continuing to the next agent decision. The pre-dispatch schedule and
final manifest both identify the `finite_evaluator_receipt_v1` contract, and
the manifest hashes the complete JSONL log. Existing historical logs without
that contract remain readable; no historical result was rewritten.

- A starter check, valid candidate submission, or explicit check gets
  `status=RAN`, the **entire structured native evaluator receipt**, and its
  SHA-256. This preserves fields such as `strong_test_result` and finite-domain
  case counts that the prior event projection dropped.
- `inspect`, `terminate`, and invalid or interrupted actions get
  `status=NOT_RUN` and a specific reason. Here `NOT_RUN` means no **valid
  completed receipt** exists; an interrupted evaluator may have started. It
  is never represented as a failed test. An infrastructure abort after a
  completed evaluation retains the receipt and marks the action invalidated.
- The full receipt lives only in the private evaluator-side log. The agent is
  given the existing public observation, which excludes the independent
  oracle, raw test channel, strong test channel, and hidden gate rule. The
  public pass/fail feedback is still delivered as designed.
  Raw, oracle, and benchmark gate values remain distinct in both the event
  projection and the archived receipt.

The v1 analysis reader checks every new record's status, digest, projected
channels, candidate and proof identity, and the complete receipt against a
fresh finite evaluator replay. An altered extra field is rejected even if the
event log and manifest hashes are recomputed. The reader also checks that the
contract in the schedule matches the manifest. These hashes establish local
integrity and source binding; a signed external freeze is still needed for
independent custody.

This records the native **structured finite checker result**, not per-case
stdout/stderr from an external executable test process. The current finite
evaluators return a binary raw test result and selected summary fields, so
per-case traces cannot be reconstructed by logging alone. A future executable
target must retain its actual raw process output or case-level receipt at the
time of each check. The proposed main trace recorder is scripted-only, runs no
evaluator, and continues to mark fixture feedback unverified. This change does
not open the main release gate or create new empirical observations.

The separate executable-catalog sandbox already returned a verifier receipt
after a source attempt or explicit security check. Its in-memory
`last_action_receipt` is now cleared before **each** tool action, so a later
`inspect` or `terminate` cannot inherit the previous check's receipt. This
corrects future log attribution; stored historical trajectories are unchanged.

Offline verification: `python3 -m unittest tests.test_v1_collector
tests.test_v1_analysis tests.test_executable_action_receipt`.
