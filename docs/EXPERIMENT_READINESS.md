# Experiment readiness — 2026-09-29

**Overall: NOT READY.** No real-agent smoke run, 3×3 pilot, or main study was launched. The engineering fixture is not an agent result. Statuses below are gates, not task-success outcomes. A failed or unrun safety check is never counted as passed.

## Git

**PASS — source baseline exists, experimental freeze does not.** The directory had no `.git` history. Git was initialized without replacing an existing repository, and an allow-listed current-study baseline was committed as `33b3d7acfc7cea0b83f96bae9f2f26d0127152da` (`git rev-parse HEAD`). `.gitignore` excludes credential files, keys, caches, future raw runs, and generated binaries. Staged paths and content were checked for common key/token signatures before the commit; this is a bounded scan, not a proof that every possible private string is absent. Legacy AVB materials were moved recoverably to the macOS Trash, not committed; see [cleanup record](LEGACY_CLEANUP.md). The pre-Git scripted fixture retains its `UNAVAILABLE_NO_GIT` sentinel and is excluded from research analysis. A later study still needs its own frozen clean commit and manifest.

## Immutable Image

**FAIL for approval; PASS for local candidate identity.** An offline `scratch`-based Linux/arm64 image was built from a Go 1.26.4 static binary. The local Docker store resolves `local/wts-target@sha256:6f32ac75f90321b56c691388eafa1a9daf2c217394eacd8c717fbb3d2ef81238` by repository digest, not by a mutable tag or arbitrary image ID. Repeating the no-attestation build retained that manifest digest. The image config has no entrypoint, volume, copied credentials, or package layer. Its [provenance](image_provenance.md) records source, binary, Dockerfile, builder versions, the distinct OCI config digest, and assumptions. **`approved_images.json` remains empty** because required runtime validation did not pass.

## Safety Suite

**FAIL.** [Candidate machine-readable result](../sandbox/safety_checks/candidate_result.json): static policy `PASS`; first runtime check `FAIL` at `docker create` because Docker rejects the existing `--pid private` option; the other eight runtime checks are `NOT_RUN_FAIL_CLOSED`. This is an unsupported invocation, **not** evidence that external network access occurred. No candidate container started, and a read-only `docker ps` check found no leftover sandbox container. The [official safety receipt](../sandbox/safety_checks/latest_result.json) remains fail-closed with zero approved images and no runtime pass. Current Docker daemon security options report `seccomp` and `cgroupns`, not daemon user-namespace remapping. No weaker flags were substituted.

| Required property | Current measurement |
| --- | --- |
| External network blocked | **FAIL to execute** first probe; actual containment NOT VERIFIED |
| Host filesystem inaccessible | **NOT_RUN** |
| Credentials absent inside runtime | **NOT_RUN** |
| Resource/CPU limits | **NOT_RUN** |
| Memory limit | **NOT_RUN** |
| Process/PID limit | **NOT_RUN** |
| Timeout termination | **NOT_RUN** |
| Cleanup after a started container | **NOT_RUN**; the rejected creation left no container |
| Reproducible runtime state | **NOT_RUN** |
| Log persistence | **NOT_RUN** |
| Fail-closed gate | **PASS**: no image was approved, `experiment_permitted` is false, and no agent episode launched |

## Benchmark

**FAIL for scientific pilot readiness; PASS for static contracts.** `python3 -m benchmark.quality --json` validates nine finite-state task definitions: three `SOLVABLE`, three `DISTRACTOR`, three `UNSOLVABLE`, with reference-plan and declared unreachability checks. This does not establish executable target correctness, distractor plausibility, or matched difficulty. In each of three task families, declared transition counts are 3/5/4 by condition, although branching factor two and six-step caps are common. Condition therefore predicts a structural difficulty proxy. No task was changed after seeing this; an independently reviewed, versioned redesign and preregistration reconciliation are required before a real pilot.

## Agent Adapter

**FAIL for a real agent.** `agent/adapter.py` defines a provider-neutral public-task lifecycle and the scripted test double verifies opaque identifiers; `agent/README.md` confirms no model SDK, network client, credentials, or provider-backed implementation. No approved provider integration, model revision, terms/budget check, or Docker-backed adapter exists. No key value was inspected or forwarded. A host-side provider client could be designed only after the safety gate and provider terms are resolved; the target would remain network-isolated.

## Smoke Test

**FAIL — NOT_RUN.** A real-agent trajectory was prohibited by the failed safety gate, unapproved image, absent provider adapter, and unvalidated executable verifier. The existing deterministic in-memory fixture is not this requested `SMOKE_TEST` and was not relabeled.

## Pilot Readiness

**NOT READY.** Resolve every blocker in [BLOCKERS.md](BLOCKERS.md), repeat candidate and official safety suites with all runtime checks `PASS`, freeze a compatible benchmark/agent/verifier revision, and only then consider exactly one excluded real smoke trajectory. Do not run the 3×3 pilot or main study yet.
