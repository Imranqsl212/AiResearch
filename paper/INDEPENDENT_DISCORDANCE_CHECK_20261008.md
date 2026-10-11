# Independent transformed-receipt check — 8 October 2026

**Scope:** a second, narrow count of the exploratory manuscript's terminal
test–gate disagreement. This note and its script are included in the v5 local
author-review bundle; the sanitized archive itself remains separate and private.
The check does not change the manuscript or any raw archive.

Run from the repository root:

```sh
python3 -B -m paper.independent_discordance_check --check
python3 -B -m unittest paper.test_independent_discordance_check -v
```

The checker uses only Python's standard library. It does **not** import
`analysis.paper_pipeline`, any of its summary functions, or
`paper.replay_sanitized_candidate`. It opens the Git-ignored transformed
review archive directly, verifies every mapped transformed member's SHA-256
and size, and checks the 40 main result-index rows against their distinct
terminal receipt objects. It checks experiment, run, task, condition,
stop/outcome and linked log-hash fields, the condition-policy reachability
flag, and the final candidate's Boolean relation to the raw family test.
For each run, discordance means the terminal candidate's embedded raw
`details.evaluator.passed` is `true` while `candidate_receipt.passed` is
`false` and the final verifier state is not `SUCCESS`.

| Directly recounted item | Count |
| --- | ---: |
| Main terminal receipts | 40 |
| Nominally unavailable (`UD`/`UW`) receipts | 20 |
| Raw family tests passed, all main receipts | 25 |
| Final candidates accepted, all main receipts | 16 |
| Raw pass followed by final rejection, unavailable receipts | **9/20** |
| Raw pass followed by final rejection, repairable receipts | 0/20 |

The four condition arms each contain ten receipts. All nine discordant
terminal candidates carry `failure_reason=condition_unreachable`. The
archive SHA-256 is
`48720a5620a1437094268452caab8f0168516454166147e575dea1c1039c0dd3`;
its sanitization manifest SHA-256 is
`a53a24fedc8f0a9f4fce2bf7d4451ebcb62cd06fc8de1d3b8ae465fc74dffef7`.
Five focused tests passed, including changes to a terminal receipt byte and
internally contradictory test/veto fields.

**Boundary:** 200 archived source members were transformed. The manifest's
claims about original member hashes and the original archive SHA cannot be
proven from these changed bytes alone. The checker reports
`original_byte_provenance_verified=false` and
`public_release_approved=false`; it neither opens nor alters the original
private archive. A [separate local original-byte audit](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md)
subsequently opened the private original and verified its byte link to the
sanitized copy, including the original terminal **9/20** count. That later
check does not broaden this transformed-only verifier's output or make either
archive publishable. This check confirms the 9/20 count within the transformed
terminal records and their internal links. It does not independently run
the family tests, establish real-world code security, validate the hidden
veto as a truthful task oracle, recover missing historical per-action raw
checks, or authorize sharing the archive. External chain-of-custody and
privacy review remain necessary for any external data package.
