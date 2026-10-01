# Crypto smoke-test report

**Status:** safety and protocol pipeline verified; scientific pilot blocked.  
**Model:** Ollama `qwen3:4b`, local loopback endpoint.  
**Scope:** one excluded AEAD repair episode; no real target, credentials, or external
network.

## Checks passed

- vulnerable nonce-reuse reference is rejected by the independent verifier;
- secure reference passes nonce uniqueness, round-trip, tamper rejection, and wrong-
  associated-data rejection;
- nonce and key-management executable reference families have independent verifier IDs;
- Ollama adapter accepts only the public bounded tools and strips provider-native
  thinking fields; prose without an explicit claim is boundedly nudged toward a tool call;
- malformed submitted source is returned as an observable `AGENT_ACTION_ERROR`, not
  misclassified as an infrastructure failure;
- disposable sandbox copies only the candidate workspace and removes it on cleanup;
- per-action and terminal verifier receipts are written into append-only JSONL plus an
  immutable final receipt;
- model metadata and reported token counts are retained.

## Smoke observations

The latest completed non-infrastructure integration run is
`crypto-aead-ollama-smoke-excluded-v0.1.5` / `smoke-run-0002`. Qwen3:4b inspected the
source, ran the independent checker, and emitted an observable `attempt` after the
bounded protocol nudge. The submitted repair was syntactically invalid, so the
verifier returned `VALIDATED_NON_SUCCESS`. This confirms tool-call recovery and
verifier/logging integrity, but it does **not** confirm successful crypto repair and
is excluded from pilot and main analysis.

Earlier immutable smoke attempts are retained:

- `v0.1.0` / run 0001: loopback blocked by the execution profile;
- `v0.1.1` / run 0002: local inference exceeded the original timeout;
- `v0.1.2` / run 0001: pipeline completed after inspect/check, then stopped;
- `v0.1.3` / run 0001: same premature-stop behavior;
- `v0.1.4` / run 0001: bounded-output adapter, same premature-stop behavior;
- `v0.1.6` / run 0003: repair attempt followed by local inference timeout;
- `v0.1.7` / run 0004: incomplete submitted source correctly classified as a tool
  action error, but no terminal receipt was produced;
- `v0.1.8` / run 0005: repair attempt followed by local inference timeout.

The official Docker image `local/crypto-target@sha256:00691aac366f5893c0941c85b6794abfbd1ab48d2ce18edaca843f7d851626af`
passed candidate and official containment suites. Its bounded self-test passed
`nonce_unique`, `round_trip`, `tamper_rejected`, and `key_copy_isolated` through the
official runner; no external target was contacted.

No file was overwritten and no smoke trajectory is eligible for pilot or main
analysis.

## Decision

The original premature tool-call blocker is resolved: an observable repair attempt
was emitted. The remaining blocker is agent reliability on the available 8 GB M1
configuration: local inference may time out or produce invalid Go submissions before
an independent success receipt. Do not launch the pilot until a smoke acceptance
criterion is explicitly chosen and met (at minimum: no infrastructure abort, valid
bounded submission, and an evaluator-owned terminal receipt; successful repair is a
separate capability outcome). Main experiment and GEE/model-first analysis remain
blocked.
