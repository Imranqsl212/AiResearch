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

This checkout is not a Git repository. Rather than invent a revision, manifests record
`git_commit: "UNAVAILABLE_NO_GIT"`. That sentinel is a reproducibility limitation, not
a source hash. Before a main study, the source must be placed in version control and
the exact commit plus uncommitted-state policy must be frozen.

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
| Confirmatory main experiment | **NOT STARTED** | All preregistration freeze gates, approved task suite, randomization schedule, provenance ledger, and safety sign-off. |

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

From the repository root, run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m experiments.run_e2e_fixture --json
```

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

Use `--require-git` for a collection gate: in this checkout it correctly fails because
the source revision is unavailable, rather than presenting the sentinel as provenance.

For any future replayable main episode, preserve the manifest, task manifest hash,
image/config digest, policy fingerprint, adapter source revision, all public action and
observation records, verifier revision, receipt digest, and a documented environment
bootstrap. The absence of any of these should be reported as a reproducibility gap.
