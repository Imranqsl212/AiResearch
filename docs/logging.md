# Observable trajectory logging

**Status:** the logging contract and a deterministic local fixture are implemented.
No provider-backed agent trace or main-experiment result has been collected.

The runner records observable behavior, not private reasoning. Its execution boundary
is deliberately asymmetric:

```text
evaluator task + hidden condition/oracle
             │ public projection only
             ▼
      AgentAdapter ── public tool call ──► EpisodeSandbox
             ▲                                  │ public observation
             └──────────────────────────────────┘
             │
             └── explicit final response

evaluator-only Sandbox result ──► independent verifier ──► append-only logger
```

The adapter never receives evaluator task/run identifiers, condition, expected outcome,
state model, reference plan, verifier, or receipt. Existing pilot task IDs and a
caller-supplied run ID can contain condition words, so `AgentTask` and `AgentRunContext`
receive opaque `public_task_id` and `public_run_id` values; the true IDs and condition
exist only in evaluator-owned logs and manifests.

## Record format

Each JSONL record conforms to
[`experiments/schemas/trajectory_event.schema.json`](../experiments/schemas/trajectory_event.schema.json).
The logger writes every field on every event, using `null`, `{}`, or `[]` when a field
does not apply. This avoids inferring event meaning from omitted fields.

| Field group | Fields | Meaning |
| --- | --- | --- |
| Identity/versioning | `experiment_id`, `run_id`, `public_run_id`, `task_id`, `public_task_id`, `condition`, `model`, `agent_version`, `benchmark_version`, `git_commit`, `timestamp` | Reconstructs the frozen episode context. `condition` and non-opaque IDs are evaluator-only metadata. |
| Observable action | `step`, `tool`, `action`, `raw_action`, `parameters` | The adapter's accepted public tool request. The runner fsyncs `TOOL_CALL` before the adapter callback or sandbox dispatch and writes `TOOL_OBSERVATION` after the sandbox returns. |
| Observable result | `observation`, `outcome`, `runtime`, `errors`, `environment_state`, `available_budget`, `token_usage` | Public tool feedback, elapsed time, bounded/redacted errors, evaluator-side state snapshot, step/time/token budgets, and provider-reported token accounting when available. |
| Behavioral annotations | `strategy`, `adaptation`, `previous_state`, `next_state` | Evaluator-side annotation. In the current finite-state fixture it comes from the declared state machine; it is not a claim about an agent's private beliefs. A production adapter may set these to `null` pending a versioned post-hoc codebook. |
| End state | `stop_event`, `verifier_result` | Distinguishes agent self-termination, budget stop, timeout, and infrastructure abort. The independent verifier receipt—not the final text—determines verified task state. |

The event stream currently uses: `TASK_HANDOFF_START`, `INITIAL_OBSERVATION`, `TOOL_CALL`,
`TOOL_OBSERVATION`, `STOP`, `VERIFIER_RECEIPT`, `ERROR`, `CLEANUP_ERROR`, and
`RUN_FINISHED`.

For the local finite-state fixture, the evaluator now checks the completed
state **after each tool action** and attaches a structured `verifier_result`
to the corresponding `TOOL_OBSERVATION`. It names
`source=evaluator_action_verifier`, the true task ID, one-based logical action
index, verifier ID/version, and outcome. The adapter receives only the public
observation, never this receipt. Prefix-length checks prevent backdating a
later success. An action-verifier error preserves the observed tool result and
aborts the episode as infrastructure failure. A locked non-aborted main run
requires a receipt on every completed action; the pre-Git fixture is validated
in legacy mode and remains excluded. A matching source string is a
format/integrity check, **not** cryptographic proof of independent authorship.
The pilot action verifier shares the authored finite-state graph with the
terminal oracle; independent executable-target verification is still absent.
The finite-state sandbox supplies a deep-copied result snapshot so verifier
code cannot mutate later sandbox evidence. Condition-dependent verifier
latency could still become a timing side channel or stopping confound.
Each action record retains `runtime.action_verifier_elapsed_seconds`. Per-action
evaluator time is included in today's wall-clock episode timeout, so
production use needs a measured overhead/censoring policy before collection.

## No chain-of-thought collection

The contract collects only:

- public tool calls and parameters;
- returned observations and outcomes;
- provider-reported token totals when the adapter has them;
- errors needed to classify infrastructure failures; and
- an explicit final response intended for the benchmark/operator.

It does not request, parse, store, or infer hidden reasoning, scratchpads, analysis
channels, chain-of-thought, or provider-native reasoning objects. The contract rejects
payload keys such as `reasoning`, `analysis`, `scratchpad`, `thought`, and
`chain_of_thought`. An explicit final response is retained as a public output, not as
a substitute for hidden reasoning.

Logs are evaluator-owned. They must not be mounted into a running agent environment:
they include true task IDs, conditions, state snapshots, and verifier receipts for
post-run analysis. Credential-like assignment text is redacted before it reaches the
JSONL stream; this is defense in depth, not permission to send a secret to an agent.

## Integrity and retention

`TrajectoryLogger` creates a JSONL path and receipt with exclusive creation mode. It
flushes and `fsync`s each event, refuses to overwrite an existing run, then stores a
SHA-256 of the closed log in the immutable receipt. The receipt contains the terminal
outcome, stop event, verifier receipt, errors, and log digest. A logging failure makes
the run unreproducible and must be classified as infrastructure failure rather than a
behavioral outcome.

`terminal_outcome` in the final receipt is an **execution-level** classification. A
budget stop or timeout remains `BUDGET_STOP` or `TIMEOUT` even if the evaluator can
describe the partially reached task state. The embedded `verifier_receipt.terminal_outcome`
is the separate task-state classification. This prevents forced stopping from being
mistaken for an agent decision or a normal task-level failure.

The current fixture writes under `experiments/runs/`. Main-study retention, access
control, encryption, and deletion policy are still **NOT IMPLEMENTED** and must be
frozen before any provider-backed episode begins.

## Scheduled slots, retries, and missingness

The main-study analysis contract now requires a seeded pre-run schedule whose
SHA-256 is stored in the manifest. A finalized all-attempt ledger names every
scheduled slot, every raw attempt, the sole selected run if any, and an explicit
reason for a missing slot. Only an `INFRASTRUCTURE_ABORT` before
`TASK_HANDOFF_START` and before any `INITIAL_OBSERVATION`, `TOOL_CALL`,
`TOOL_OBSERVATION`, or agent `STOP` can be retried, at most twice. The
evaluator fsyncs `TASK_HANDOFF_START` before calling `adapter.provide_task`;
task handoff already makes an abort non-retryable, even with no tool call.
Such an abort remains the selected slot outcome. The input lock hashes the schedule,
ledger, every log and receipt, and all task definitions. Unlisted files or
contradictory retries stop analysis. The append-once metadata writer
[`AttemptLedgerWriter`](../experiments/attempt_ledger.py) now reserves each attempt
before execution, verifies the raw log/receipt on completion, blocks unresolved
reservations, and emits the final all-slot ledger. It has only synthetic
engineering tests; it is not wired to a provider runner or an immutable
raw-data store, and it does not make the study collection-ready.

## Meaning of “adaptation” in logs

The logger does not inspect or label private mental states. It preserves enough
observable sequence information for a later pre-specified classifier to distinguish:

- repeated action;
- parameter change;
- tool change;
- implementation change;
- hypothesis-level change; and
- strategy-level change.

For the finite-state pilot only, the transition manifest supplies `strategy`,
`adaptation`, `previous_state`, and `next_state` deterministically. That annotation is
useful for an integration fixture but is not evidence that a real agent adopted a
strategy. Main-study annotations require the preregistered codebook, calibrator
agreement, and versioned derivation code specified in
[`docs/preregistration.md`](preregistration.md).
