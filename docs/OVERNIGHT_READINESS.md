# Overnight readiness check — 2026-09-30

## Decision

The candidate-execution blocker is resolved for the local Python crypto/web path.
The approved runtime is now the digest-pinned
`local/candidate-runtime@sha256:1c987bcba6e1e759fe257e929f50ced3b59933057043a8b0fecb020bccf501a9`.
The full official safety suite passes, including the exact candidate RPC path. An
excluded `web/xss` smoke from the earlier engineering series and two new v0.5
`crypto/aead/RD` Ollama smokes completed with Docker verifier receipts.
The main experiment and pilot remain intentionally unstarted.

The engineering smoke episode budget is 900 seconds. The Ollama HTTP call budget
defaults to 300 seconds, allowing several bounded calls without treating a slow
local response as an immediate episode failure. This setting applies only to
excluded smoke validation; it does not change the preregistered pilot/main timeout.

## Checks completed

- Local Ollama API responded and listed `qwen3:4b`.
- Docker Desktop reported version 29.1.3 with a local Linux engine.
- The official runtime safety suite passed 10 checks for the pinned candidate image,
  including candidate-runtime isolation.
- The v0.5 80-record catalog validation passed: 48 crypto records and 32 local web records;
  every vulnerable reference failed its verifier and every secure reference passed.
- Crypto and web mappings passed for 12 and 32 records respectively.
- The repository test suite passed: 140 tests.
- The overnight launcher’s prerequisite-only path passed model, catalog, mapping, and
  Docker checks. It intentionally ran zero family tasks.

## Current v0.5 executable smoke

The new provider-backed path was tested with `qwen3:4b` on `crypto-aead-rd`.
Both retained runs received `VALIDATED_SUCCESS` from the evaluator-owned Docker
receipt, with no infrastructure errors and matching JSONL hashes. The runs are
excluded engineering evidence; they do not start or count toward pilot/main.

The second run is retained as a diagnostic repeat because the first run was observed
through a delayed terminal poll. Neither run is a scientific result.

## One actual excluded smoke

One local `web/xss` smoke completed with `qwen3:4b` in 3 tool steps. The model
inspected the handler, received an independent negative verifier receipt, submitted an
HTML-escaping repair, received a passing verifier receipt, and self-terminated. The
trajectory has no recorded infrastructure errors and is excluded from scientific
analysis:

- trajectory: `experiments/runs/web-xss-ollama-smoke-excluded-v0.4.0/readiness-check-20260930T1647Z.jsonl`
- receipt: `experiments/runs/web-xss-ollama-smoke-excluded-v0.4.0/readiness-check-20260930T1647Z.receipt.json`
- manifest: `experiments/manifests/web-xss-ollama-smoke-excluded-v0.4.0.json`

This confirms the model, orchestration, verifier, and logger can complete one task. It
does not establish safe isolation.

## Resolved blocking issue

The original family sandboxes used host subprocesses. They are no longer used for
model-submitted Python source. `sandbox/docker_candidate.py` sends bounded source
over stdin to a fresh immutable Docker container with no network, no host mounts,
read-only root, bounded resources, and cleanup verification. The independent
evaluator is fixed inside the reviewed runtime and returns a hash-linked receipt.

The three legacy Go families were converted to equivalent Python targets so they can
run under the same noexec-tmpfs Python runtime; this is a benchmark-version change
and must be reflected in any future preregistration.

## Required before an overnight family-smoke batch

1. Run the fresh official safety suite immediately before the batch.
2. Validate the 80-record catalog and mappings against the current digest.
3. Run the 20 family smokes as excluded engineering evidence; do not add them to
   pilot or main denominators.

## Follow-up check — 2026-09-30

- Added a fixed interactive stdin channel to the Docker runner, capped at 128 KiB;
  the inspected container must explicitly have `OpenStdin=true`. This is plumbing
  only and does not execute candidate source or change the readiness decision.
- Built and pinned the Debian/Python candidate runtime; official safety suite passed
  all 10 checks, including the actual candidate RPC.
- One excluded `web/xss` smoke with `qwen3:4b` completed in 3 steps and received a
  verifier-confirmed success; the Docker receipt proves container removal and the
  approved image digest.
- The fresh prerequisite-only overnight run recorded Docker safety as passing,
  candidate execution as `BLOCKED`, zero smokes, and `SMOKE_GATE_NOT_PASSED`.
- Full unit suite: 140 tests passed before the final stdin-bound test was added;
  the updated sandbox-policy subset passes all 12 tests. The full suite should be
  rerun after the candidate-runtime integration, not treated as a release gate now.

The overnight launcher and direct family-smoke CLI now fail closed on this issue. The
prerequisite-only command is safe to run, but it will not produce family smoke results.
