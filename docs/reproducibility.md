# Reproducibility and run provenance

**Status:** a versioned manifest format, append-only observable log, receipt digest,
and deterministic in-memory smoke fixture are implemented. The main experiment is
still blocked: no approved runtime image, provider-backed adapter, frozen provider
configuration, or live experiment trace exists.

## What is frozen for every run

An [`ExperimentManifest`](../experiments/manifest.py) is written before its run record.
The machine-readable schema is
[`experiments/schemas/experiment_manifest.schema.json`](../experiments/schemas/experiment_manifest.schema.json).
It records:

- `model` and `agent_version`;
- `benchmark_version`, `task_ids`, task count, and runs per task;
- `temperature`, maximum steps, timeout, optional token budget, and seed;
- `adapter_type`, `sandbox_type`, and `safety_mode`;
- date and timestamp; and
- the Git commit when available.

For future main studies the manifest must also carry a `schedule_sha256`.
The seeded, family/repeat-blocked schedule is written before collection;
the finalized all-attempt ledger is written after it. The analysis input lock
now verifies both artifacts, every scheduled slot, all attempts (including
setup failures), and all raw file hashes. This prevents complete-case analysis
from silently forgetting missing slots. A metadata-only create-once
reservation/completion journal now emits a lock-compatible final ledger and
has synthetic failure-injection tests. It rejects an unresolved reservation
after restart, raw mutation, duplicate run IDs, orphan files, and retries
after task handoff starts. This is not a signed or access-controlled archive:
filesystem owners can still change records. No real study schedule, provider
orchestration, immutable raw archive, or collection freeze exists yet.

Git was initialized without altering any pre-existing history (none existed), and the
first inspected When-to-Stop infrastructure baseline was committed as
`33b3d7acfc7cea0b83f96bae9f2f26d0127152da` (`git rev-parse HEAD` immediately
after the initial commit). This records code and documentation, **not** a frozen
experimental configuration. The older scripted fixture was created before Git and
retains `git_commit: "UNAVAILABLE_NO_GIT"`; its receipt must not be retroactively
rewritten. Every future real run must record its own exact commit and a clean or
explicitly archived working-tree state.

Manifests and run records are immutable at the path level: manifest configuration may
only be reused if it is identical; logs and receipts are created with exclusive mode;
a receipt contains the SHA-256 of its closed JSONL log. A different run requires a new
run ID. A different configuration requires a new experiment ID.

## Determinism tiers

| Tier | Current status | Required evidence |
| --- | --- | --- |
| Declarative task transition | Implemented for the nine local pilot tasks | Repeated state-machine simulation and independent validator receipt agree. |
| Adapter/sandbox integration fixture | Implemented | `ScriptedFixtureAdapter` has a fixed action list; `InMemoryFiniteStateSandbox` has no process, network, credential, or mutable host state. |
| Containerized local episode | **NOT IMPLEMENTED / blocked** | Reviewed immutable image/config digest, passing complete safety suite, policy fingerprint, and reproducible task state. |
| Provider-backed agent run | **NOT IMPLEMENTED** | Frozen model/revision, prompts, tools, permissions, SDK/runtime, sampling settings, provider region/endpoint policy, retries, and provider response metadata. |
| Confirmatory main experiment | **NOT STARTED** | All preregistration freeze gates, approved task suite, actual pre-run randomization schedule and finalized provenance ledger, and safety sign-off. |

The smoke fixture is deterministic because its adapter is a hard-coded test double, not
because real language-model behavior is assumed deterministic. Its seed is recorded as
`0` for provenance only. It produces zero provider-agent runs and is excluded from all
scientific analysis.

## Limits of real-agent reproducibility

Even with a fixed seed, an API-backed agent may vary because of an unpinned model
revision, nondeterministic decoding/kernel execution, provider-side changes, retries,
tool latency, rate limits, or hidden service configuration. A future adapter must
record what it can observe, including provider-reported token usage and response/model
metadata allowed by policy. It must not log private chain-of-thought to compensate for
that uncertainty.

The runner currently enforces step and wall-time checks at decision/tool boundaries.
A future provider adapter must honor the frozen deadline, and an image-backed runtime
must additionally be bounded by the fail-closed Docker policy. A blocking provider call
cannot be safely killed by the generic in-process interface; that is an explicit
design constraint to resolve before provider-backed execution, not a reason to weaken
the sandbox.

## Replay procedure for the implemented fixture

The committed fixture predates Git and uses benchmark v0.1.0. It must remain immutable. The current task manifests are v0.1.1, so the **old default experiment ID cannot be reused** with a current Git commit; merely changing the run ID does not resolve the manifest conflict. From the repository root, create a fresh disposable output root and a distinct engineering-only experiment ID:

```sh
fixture_output_root="$(mktemp -d)"
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.run_e2e_fixture \
  --output-root "$fixture_output_root" \
  --experiment-id engineering-replay-v011 --run-id replay-0001 --json
```

This writes only under the new temporary root; it does not overwrite the tracked v0.1.0 fixture. Compare semantic event sequence and verifier outcome, not timestamps, opaque identifiers, Git hash, or version fields. This is **not** a provider-agent or Docker reproduction.

The command performs one local finite-state path through:

```text
benchmark task → scripted fixture adapter → in-memory sandbox → independent verifier → JSONL + receipt
```

It never creates a Docker container, calls a model provider, uses credentials, opens a
network connection, or contacts an external target. It exits successfully only if the
independent receipt passes. Re-running with the same run ID intentionally fails rather
than overwriting the original artifact; use a new run ID for a separate smoke run.

Validate an already-created artifact without replaying it:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m experiments.validate_artifacts \
  --manifest experiments/manifests/e2e-local-finite-state-v0.1.2.json \
  --log experiments/runs/e2e-local-finite-state-v0.1.2/fixture-run-0001.jsonl \
  --receipt experiments/runs/e2e-local-finite-state-v0.1.2/fixture-run-0001.receipt.json \
  --json
```

Use `--require-git` for a collection gate: it correctly rejects the pre-Git fixture's
sentinel even though the repository now has a baseline commit. This preserves the
historical provenance boundary rather than laundering an old trace into main data.
The v0.1.4 [fixture reproduction command](../experiments/README.md) instead
writes to a fresh temporary directory and checks `--require-action-verifier`;
the main analysis input lock requires that check for non-aborted attempts.

For any future replayable main episode, preserve the manifest, task manifest hash,
image/config digest, policy fingerprint, adapter source revision, all public action and
observation records, verifier revision, receipt digest, and a documented environment
bootstrap. The absence of any of these should be reported as a reproducibility gap.
