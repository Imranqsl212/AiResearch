# Experiment readiness — 2026-09-30

**Overall: NOT READY.** No real-agent smoke run, 3×3 pilot, or main study was launched. The engineering fixture is not an agent result. Statuses below are gates, not task-success outcomes. A failed or unrun safety check is never counted as passed.

**Safety update (same date):** [Machine-readable readiness](../experiments/readiness.json) remains `NOT_READY` overall, but the safety gate is now `PASS`. Docker Desktop reports context `desktop-linux`, LinuxKit kernel, `OSType=linux`, Docker Desktop identity, and seccomp; the policy records this as `docker-desktop-linuxkit-vm`, not daemon userns-remapping. The official suite passed all nine runtime checks for the exact immutable image digest and records `experiment_permitted=true`. This clears only the sandbox gate. The v0.1.1 engineering pilot remains condition-confounded; the four-cell development suite, executable verifier, provider agent, protocol freeze, and scientific readiness are still incomplete. Passing safety tests does not establish scientific readiness.

## Git

**PASS — source baseline exists, experimental freeze does not.** The directory had no `.git` history. Git was initialized without replacing an existing repository, and an allow-listed current-study baseline was committed as `33b3d7acfc7cea0b83f96bae9f2f26d0127152da` (`git rev-parse HEAD`). `.gitignore` excludes credential files, keys, caches, future raw runs, and generated binaries. Staged paths and content were checked for common key/token signatures before the commit; this is a bounded scan, not a proof that every possible private string is absent. Legacy AVB materials were moved recoverably to the macOS Trash, not committed; see [cleanup record](LEGACY_CLEANUP.md). The pre-Git scripted fixture retains its `UNAVAILABLE_NO_GIT` sentinel and is excluded from research analysis. A later study still needs its own frozen clean commit and manifest.

## Immutable Image

**PASS for sandbox approval; not scientific readiness.** An offline `scratch`-based Linux/arm64 image was rebuilt from a Go static binary. The local Docker store resolves `local/wts-target@sha256:1f02d5aae10c93fac5b1a19264ad05f4b2112271549fb161921c14ce26853636` by immutable digest. The image config has no entrypoint, volume, copied credentials, or package layer. Its [provenance](image_provenance.md) records source, binary, Dockerfile, builder versions, and assumptions. The approval covers only the fixed local runner/safety-probe policy.

## Safety Suite

**PASS — sandbox gate only.** The [candidate result](../sandbox/safety_checks/candidate_result.json) and [current official safety receipt](../sandbox/safety_checks/latest_result.json) record static `PASS` and **all nine runtime checks `PASS`** for the new digest. The receipt records `experiment_permitted=true`, `agent_runs_launched=0`, `external_targets_contacted=false`, and `isolation_mode=docker-desktop-linuxkit-vm`. No provider-backed agent or scientific episode was launched. Docker Desktop VM escape resistance remains an explicit residual assumption.

| Required property | Current measurement |
| --- | --- |
| External network blocked | **PASS** |
| Host filesystem inaccessible | **PASS** |
| Credentials absent inside runtime | **PASS** |
| Resource/CPU limits | **PASS** |
| Memory limit | **PASS** |
| Process/PID limit | **PASS** |
| Timeout termination | **PASS** |
| Cleanup after a started container | **PASS** |
| Reproducible runtime state | **PASS** |
| Log persistence | **PASS** |
| Fail-closed gate | **PASS**: exact image/policy/daemon receipt is valid; no agent episode launched |

## Benchmark

**FAIL for scientific pilot readiness; PASS for static contracts.** The legacy
`python3 -m benchmark.quality --json` validates nine v0.1.1 finite-state engineering
tasks. A separate `python3 -m benchmark.quality_four_cell --json` now validates a
12-manifest v0.2.0 development suite with three families and exactly one `RD`, `UD`,
`RW`, and `UW` cell per family, identical public projections, tool contracts, and
transition counts. This is progress on the matched-design blocker, not proof of
executable target correctness, distractor validity, unreachability, or agent behavior.
The Docker-backed target, independent runtime verifier, and preregistration freeze are
still required before a real pilot.

## Agent Adapter

**FAIL for a real agent.** `agent/adapter.py` defines a provider-neutral public-task lifecycle and the scripted test double verifies opaque identifiers; `agent/README.md` confirms no model SDK, network client, credentials, or provider-backed implementation. No approved provider integration, model revision, terms/budget check, or Docker-backed adapter exists. No key value was inspected or forwarded. A host-side provider client could be designed only after the safety gate and provider terms are resolved; the target would remain network-isolated.

**Finite-state timing instrumentation only:** the v0.1.4 scripted fixture now logs
an evaluator-owned task-handoff marker before provisioning and a completed-prefix
verifier receipt after each tool action.
Temporary replay and strict artifact validation pass, and the main input lock
requires such receipts for non-aborted runs. The authored graph is still its
own oracle; no independently reviewed executable-target action verifier or
provider-backed behavior has been measured. This does not change `NOT_READY`.

## Smoke Test

**FAIL — NOT_RUN.** A real-agent trajectory was prohibited by the failed safety gate, unapproved image, absent provider adapter, and unvalidated executable verifier. The existing deterministic in-memory fixture is not this requested `SMOKE_TEST` and was not relabeled.

## Pilot Readiness

**NOT READY.** Resolve every blocker in [BLOCKERS.md](BLOCKERS.md), repeat candidate and official safety suites with all runtime checks `PASS`, freeze a compatible benchmark/agent/verifier revision, and only then consider exactly one excluded real smoke trajectory. Do not run the 3×3 pilot or main study yet.
