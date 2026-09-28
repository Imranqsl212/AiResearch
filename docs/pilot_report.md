# Controlled Pilot Preflight Report

**Project:** *When to Stop: How AI Agents Adapt After Failed Attacks and Why They Fail to Give Up*  
**Report status:** **BLOCKED AT PREFLIGHT — no real agent pilot was run**  
**Scope:** requested 3 SOLVABLE + 3 DISTRACTOR + 3 UNSOLVABLE controlled pilot; no full benchmark and no external target.

## Executive decision

The controlled pilot is not scientifically or technically eligible to start. The
fail-closed Docker safety suite reports `experiment_permitted: false`: there is no
reviewed, immutable, safety-test-eligible image in
[`sandbox/images/approved_images.json`](../sandbox/images/approved_images.json).
Additionally, this checkout has no Git repository, so a main or real-agent pilot cannot
record an immutable source revision.

No provider-backed agent, containerized task, external target, credential, network
connection, or main-experiment episode was launched. The only existing end-to-end trace
is a deterministic in-memory **scripted fixture**; it is an engineering test double,
not a participant, baseline, or pilot result.

## Preflight validation rubric

| Criterion | Evidence required | Result |
| --- | --- | --- |
| Containment | Full safety suite passes, including all runtime checks | **FAIL / fail-closed**: static policy passed; nine runtime checks were `NOT_RUN_FAIL_CLOSED` because no reviewed image exists. |
| Task ground truth | All 9 task contracts, reference paths, and condition checks pass | PASS for the static finite-state fixture. |
| Independent verification | Every reference path receives a verifier receipt; tampering is rejected | PASS for the static fixture. |
| Observable logging | Manifest/log/receipt are internally consistent, no forbidden reasoning fields, digest matches | PASS for the scripted fixture; strict provenance gate fails because Git is unavailable. |
| Provenance | Immutable source revision is recorded | **FAIL**: `git rev-parse --verify HEAD` exits 128; manifest contains `UNAVAILABLE_NO_GIT`. |

The first and fifth criteria are collection gates. Passing the remaining static checks
does not override them.

## Setup actually exercised

| Component | State |
| --- | --- |
| Task set | 9 local finite-state tasks: 3 SOLVABLE, 3 DISTRACTOR, 3 UNSOLVABLE across scope, integrity, and precondition families. |
| Agent | No real agent configured. `ScriptedFixtureAdapter` was used only for pre-existing wiring tests. |
| Sandbox | No Docker task sandbox was started. The fixture uses `InMemoryFiniteStateSandbox`, which has no subprocess, network, credential, shell, or host-filesystem mutation capability. |
| Verifier | `pilot_state_machine_v1`, evaluator-owned and independent of an agent's final claim. |
| Logging | Versioned manifest, append-only JSONL, SHA-256 receipt, public task/run IDs at the adapter boundary, and no-private-reasoning guard. |
| Run count | Real agent runs: **0**. Scripted fixture episodes retained as engineering evidence: **1**. |

## Preflight checks and results

### Safety and runtime inventory

`python3 -m sandbox.safety_checks.run --json` produced:

- `static_policy_locked`: PASS;
- nine runtime checks (`external_network_blocked`, host filesystem, credentials,
  cleanup, limits, timeout, runaway process, logs, reproducibility):
  `NOT_RUN_FAIL_CLOSED`;
- `experiment_permitted: false`, `agent_runs_launched: 0`, and
  `external_targets_contacted: false`.

The exact receipt is
[`sandbox/safety_checks/latest_result.json`](../sandbox/safety_checks/latest_result.json).
Read-only Docker inventory showed one untagged/dangling local image and only exited
containers. Neither is a reviewed immutable image, so neither was started, tagged,
approved, modified, or used.

### Task and verifier validation

`python3 -m benchmark.quality --json` passed all 9 task manifests:

| Condition | Static task count | What the validator established | Result |
| --- | ---: | --- | --- |
| SOLVABLE | 3 | Goal state is graph-reachable; evaluator-owned reference plan reaches it and the independent receipt is `VALIDATED_SUCCESS`. | 3/3 PASS |
| DISTRACTOR | 3 | First reference action receives `HYPOTHESIS_REFUTED`; a later action has meaningful adaptation and changes declared strategy before verified success. | 3/3 PASS |
| UNSOLVABLE | 3 | Goal state is graph-unreachable; reference path obtains conclusive unavailable evidence and explicitly terminates in the declared stop state. | 3/3 PASS |

The suite also exercises verifier independence: a manifest whose expected state is
tampered is rejected as `INVALID_TASK`, and a success claim on an unavailable state is
recorded as unsupported. These are checks of the declarative fixture, not evidence that
a real agent will distinguish the conditions.

### Manifest and logging validation

The retained wiring fixture is:

- [manifest](../experiments/manifests/e2e-local-finite-state-v0.1.2.json)
- [JSONL trajectory](../experiments/runs/e2e-local-finite-state-v0.1.2/fixture-run-0001.jsonl)
- [verifier receipt](../experiments/runs/e2e-local-finite-state-v0.1.2/fixture-run-0001.receipt.json)

`experiments.validate_artifacts` reports 8 contiguous records, a matching SHA-256
receipt, a verifier receipt, an explicit stop event, and no private-reasoning payload
fields. It passes in advisory mode. With `--require-git`, it fails exactly because the
manifest's Git revision is unavailable. That strict failure is correct and is a
collection blocker, not a logging defect.

The full Python test suite passes 28 tests, including task quality, verifier tampering,
public task/run label isolation, false-success retention, artifact integrity, budget
stop, and timeout classification.

## Answers to pilot questions

| Question | Evidence-backed answer | Boundary |
| --- | --- | --- |
| Are tasks distinguishable? | Structurally yes: the state graphs and reference contracts differ in reachability/evidence behavior. | Whether an AI recognizes that distinction is **unknown**; no real agent run exists. |
| Are solvable tasks solvable? | Yes for the evaluator-owned finite-state reference paths (3/3). | Not yet demonstrated for a real agent or image-backed task. |
| Are unsolvable tasks actually unsolvable? | Yes within the declared finite-state graph: the goal is unreachable and the reference termination is validator-confirmed (3/3). | This is a model-relative proof; it does not validate a future richer implementation automatically. |
| Are distractors meaningful? | The declared distractor actions receive diagnostic refutation, followed by a declared meaningful transition (3/3). | This proves task construction, not that an agent finds the distractor plausible. |
| Does the verifier work? | It accepts expected reference states, rejects manifest/oracle disagreement, and marks an unsupported success claim. | Only the local state-machine verifier has been exercised. |
| Are logs complete? | The scripted fixture has a complete 8-event JSONL stream and matching receipt digest. | Provider/model telemetry and image-backed logs remain untested. |
| Are failures classified correctly? | **Improved and covered by tests.** `BUDGET_STOP` and `TIMEOUT` are now execution outcomes, while `verifier_receipt.terminal_outcome` separately records task state. | No live provider or Docker failure has been observed. |
| Are stopping events observable? | Yes in the fixture: `AGENT_SELF_TERMINATION`, `BUDGET_STOP`, `TIMEOUT`, and `INFRASTRUCTURE_ABORT` have distinct records. | Observability does not establish rationality. |
| Can strategy changes be separated from action changes? | In the finite-state fixture, yes: evaluator annotations retain action, parameter, strategy, adaptation, previous state, and next state. | For real agents, these require the preregistered post-hoc codebook; they are not hidden-belief measurements. |
| Are metrics redundant? | No: execution terminal outcome, stop event, verifier task-state outcome, claim support, and action/strategy annotations answer different questions. | Their empirical correlation cannot be estimated without real trajectories. |
| Are there confounders? | Yes; see below. | These prevent treating static fixture success as pilot evidence. |

## Infrastructure, benchmark, and logging failures

### Infrastructure failures

1. **Blocking:** no reviewed immutable safety-test image. The safety suite correctly
   failed closed before any container could start.
2. **Blocking:** no Git revision. The `UNAVAILABLE_NO_GIT` sentinel makes strict
   artifact provenance fail.
3. **Not a task failure:** no provider-backed adapter is configured, so the requested
   multiple-runs-per-task design has no available agent budget/runtime.

### Benchmark failures

No static contract failure was found in the nine finite-state manifests. This is not a
claim that the benchmark is scientifically ready: the task surface is intentionally
small and declarative, so it does not yet approximate an image-backed security task or
test robustness to model/tool variation.

### Logging failures

No integrity failure was found in the retained scripted fixture. A provenance warning
becomes a strict failure when Git is required. Provider token accounting, retries,
transport errors, container cleanup receipts, and runtime-hidden validator isolation
remain **NOT IMPLEMENTED** for real agent episodes.

## Unexpected behavior and scientific concerns

There is no agent behavior to interpret. The important negative result is operational:
the project prevents collection before containment and provenance are defensible.

Key scientific concerns remain:

1. A reference plan proves only that the finite-state task is internally consistent;
   it cannot measure an agent's exploration, persistence, or hypothesis abandonment.
2. The current strategy/adaptation labels come from evaluator state transitions. They
   must not be reported as a real agent's private strategy without the preregistered
   observable codebook and calibration.
3. Three matched task families are sufficient for an engineering pilot but not to
   disentangle condition, task family, prompt wording, and action-space difficulty.
4. An opaque ID prevents trivial label leakage through names, but it does not address
   model pretraining contamination or hidden oracle leakage in a future container.
5. Step/time budgets can censor behavior; the new separation of execution stop from
   verifier state prevents one classification error, but calibration still needs actual
   traces before the confirmatory budget is frozen.

## Fixes implemented during preflight

These are instrumentation/integrity repairs, not changes to the preregistered research
questions, conditions, hypotheses, estimands, or sample plan:

1. Added opaque `AgentRunContext.public_run_id` in addition to opaque task IDs, so a
   condition-bearing evaluator run ID cannot reach an adapter. Regression tests use
   deliberately condition-bearing evaluator IDs.
2. Split execution terminal classification from verifier task-state classification.
   A forced budget stop or timeout is no longer labeled as a normal task-level
   non-success simply because the verifier can describe the partial state.
3. Added `experiments.validate_artifacts`, which checks manifest/log/receipt identity,
   contiguous JSONL sequence, schema fields, no-private-reasoning payload policy,
   verifier-event presence, and receipt SHA-256. `--require-git` exposes missing source
   provenance as an explicit gate failure.
4. Added deterministic tests for budget stopping, timeout, unsupported final success,
   artifact integrity, and public identifier isolation.

## Required fixes before rerunning this pilot

1. An authorized owner must select or build a **known-source** local image, review its
   Docker config and digest, record its purpose, and add exactly that immutable digest
   to the image allow-list. The untagged local image must not be self-approved merely
   because it exists.
2. Run the complete safety suite against that reviewed image. All runtime checks must
   pass; any failure remains a no-run condition.
3. Restore or initialize an agreed version-control baseline and record a real commit
   (plus clean/dirty policy). Do not substitute an invented hash.
4. Implement and freeze a provider-backed adapter configuration, including model
   revision, prompt/tool policy, timeout behavior, retries, and token accounting.
5. Conduct the requested 3 × 3 real-agent instrumentation pilot only after steps 1–4,
   keeping all results explicitly non-confirmatory and recording any protocol version
   change before collection.

## Protocol-impact statement

No preregistered methodology was silently changed. The new public-run identifier,
artifact validator, and execution-vs-verifier terminal split implement existing
requirements to avoid label leakage, retain complete traces, and distinguish timeout or
budget stopping from voluntary termination. They are documented as implementation
integrity changes below and do not authorize main-experiment collection.

## Final pilot disposition

**DO NOT PROCEED TO THE MAIN EXPERIMENT.** The requested real controlled pilot has not
started because safety and provenance gates fail. The next safe action is image/source
provenance approval, followed by a complete passing safety suite—not relaxing the gate
or interpreting scripted fixtures as agent evidence.
