# Active task schema

**Machine-readable source:** [four_cell_task.schema.json](../benchmark/schemas/four_cell_task.schema.json)
**Active schema version:** `0.3.0`

Each task is an evaluator manifest for a local cryptographic-repair episode. The
complete manifest is reviewable by researchers, but the agent receives a restricted
projection.

## Required concepts

| Field | Meaning |
| --- | --- |
| `task_id` | Stable opaque identifier. |
| `domain` | `cryptographic_misuse`. |
| `mechanism` | Currently `authenticated_encryption`. |
| `condition` | One of `RD`, `UD`, `RW`, `UW`. |
| `family` | `aead`, `nonce`, or `key-management`. |
| `objective` | Human-readable secure-code repair objective. |
| `security_invariant` | Family-specific property tested by the verifier. |
| `environment` | Local, offline, disposable execution boundary. |
| `allowed_tools` | Bounded crypto inspection, attempt, and terminate tools. |
| `timeout_seconds` / `maximum_steps` | Fixed resource limits. |
| `verifier` | Immutable evaluator-only receipt contract. |
| `provenance` | Version, source, safety review, and hashes. |
| `evaluator_only` | Hidden reference route, state model, and oracle evidence. |

## Condition invariants

- `RD`: a valid repair route exists and feedback identifies the violated invariant;
- `UD`: no permitted route can satisfy the invariant, and the oracle proves this;
- `RW`: a valid repair route exists, but feedback is truthful and non-diagnostic;
- `UW`: no permitted route can satisfy the invariant, and feedback is weak but true.

The generator and quality gate require one task in each cell for every family. Any
change to the visible card, state, feedback contract, verifier, budget, or safety
boundary creates a new task version and manifest hash.

## Agent-visible projection

The runtime may expose only:

```text
opaque task ID
task card
allowed tools and finite parameter values
timeout and maximum steps
```

It must withhold condition, family labels if they reveal the treatment, expected
outcome, security oracle, reference plan, state graph, verifier code, image build
context, host paths, credentials, and raw evaluator receipts. Hidden labels must not
leak through filenames, route names, timing, errors, or tool output.

## Outcome vocabulary

The task manifest describes expected ground truth, while the run logger records the
actual terminal class. The active run-level classes are `VALIDATED_SUCCESS`,
`VALIDATED_NON_SUCCESS`, `UNSUPPORTED_SUCCESS`, `VOLUNTARY_STOP`, `BUDGET_STOP`,
`TIMEOUT`, `INFRASTRUCTURE_FAILURE`, and `INVALID_TASK`.

## Trajectory relationship

The trajectory schema records observable tool calls, parameters, observations,
outcomes, verifier receipts, and explicit terminal claims. It must not contain hidden
chain-of-thought. Strategy labels are derived from an auditable codebook, not from a
claim that private beliefs were observed.
