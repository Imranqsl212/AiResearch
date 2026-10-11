# Excluded live dispatch boundary — 5 October 2026

[`experiments/main_live_dispatch_excluded.py`](../experiments/main_live_dispatch_excluded.py)
adds a transport-injected byte recorder for one **excluded pilot** slot of the
ungated proposed plan. No model endpoint is configured or contacted by this
module itself. The tests inject an in-memory fake transport; no new model run
was made. Every recorder-issued phase field uses `phase=pilot`,
`eligible_for_main_analysis=false`, and `main_dispatch_allowed=false`.
`plan_snapshot.json` preserves the proposed plan's original `phase=main` only
as design metadata, never as an observation.

The recorder verifies the slot's model name/digest, six-decision inference
config, task/proof hashes, and complete source inventory before reserving a
new output directory. For each call it rechecks source bytes and transport
model identity, validates the exact serialized request, then writes the raw
request and a pre-dispatch record. Both files and their directory entries are
`fsync`ed **before** `transport.send` receives the same byte object. The raw
response and return record are archived before any action parsing. File
creation is exclusive, raw files are mode `0600`, and the slot directory is
mode `0700`.

The transport can only send to the frozen `/api/chat` path. One parsed
response consumes one decision when `record_decision` is called; submissions
are counted separately. A caller-supplied `PASS` is marked as **unverified**
feedback and does not stop collection. Only `terminate`, `claim`, timeout, or
the six-decision budget can close a completed slot. An exception, malformed
response, source/model drift, or archive failure invalidates it. The directory
cannot be reopened as a replacement. The receipt retains dispatch attempts,
failure type, interruption record when possible, and any raw file that was
written before its manifest entry failed. The offline verifier rehashes raw
and source bytes and checks the action/decision accounting.

Run `python3 -B -m unittest -v tests.test_main_live_dispatch_excluded`.
Twelve fake-transport tests pass. A fake send callback checks that the exact
request and pre-dispatch record already exist and that file and directory
`fsync` calls occurred before send. Negative tests cover transport timeout,
malformed response, wrong request seed, model digest drift, initial identity
mismatch, failed pre-dispatch archive, failed response archive, and raw-byte
tampering. They also cover a keyboard interrupt, source drift, and a return
receipt failure after the raw response is saved. No test promotes a trace to
main. Nonstandard numeric `NaN` in a candidate is archived and invalidated as
a protocol failure.

## Remaining proof gaps

- A fake transport proves the wrapper's call order, not actual Ollama model
  execution or digest truth. An [opt-in local HTTP transport](MAIN_OLLAMA_TRANSPORT_EXCLUDED_20261005.md)
  now exercises the byte interface in no-network tests. No real model call or
  main-eligible trace is produced by those tests.
- The request body is checked for frozen options, but this module does not
  reconstruct the public task, accumulated observations, R1 retrieval, or
  evaluator feedback. It does not validate task-specific candidate shape or
  compute an independent security oracle. Its completed status is explicitly
  `COMPLETED_EXCLUDED_UNVERIFIED`.
- A hard process kill or total storage failure can leave an open directory
  without a final receipt; the write-once directory prevents a silent retry.
  The [read-only crash audit](EXCLUDED_LIVE_DISPATCH_CRASH_AUDIT_20261005.md)
  now classifies the surviving artifacts without recovery or replacement.
- Exact raw responses may contain sensitive or hidden provider fields. These
  pilot archives are private and require privacy review before any release.
  The verifier checks hashes, not authenticity against an external trusted
  timestamp or signed provider receipt.
- The final source-commit-bound schedule, admitted 20-family catalog and R1
  corpus, live C5 fork, main collector gate, and main release reader remain
  separate. This module cannot emit an eligible main observation.
