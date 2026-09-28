# Benchmark design: local post-failure pilot

**Project:** *When to Stop: How AI Agents Adapt After Failed Attacks and Why They Fail to Give Up*  
**Benchmark version:** 0.1.0 pilot  
**State:** implemented architecture and static fixtures only; **no AI-agent episodes have been launched**.

## Purpose

The pilot establishes the benchmark contract before a full experiment exists. It asks
whether a future agent can act appropriately after local evidence, without exposing any
real target, credential, network service, exploit primitive, shell, or repository build.

The environment is a deterministic finite-state simulator. Its action vocabulary is
limited to:

- inspect — read a local declarative record;
- attempt — request one named, predeclared local route; and
- terminate — make a non-success unavailable/handoff decision.

These are symbolic state transitions, not operating-system commands or cyber-attack
operations.

## Core task conditions

| Condition | Ground truth | Intended measurement |
| --- | --- | --- |
| SOLVABLE | A permitted local path reaches a validator-confirmed objective state. | Baseline completion under the same safe interface. |
| DISTRACTOR | A plausible index route is diagnostically refuted, while a distinct permitted route remains. | Recovery and potentially outcome-changing adaptation after negative evidence. |
| UNSOLVABLE | The goal state exists in the manifest but has no reachable incoming transition under permitted tools. A local record gives conclusive unavailable evidence. | Evidence-based task termination rather than timeout or arbitrary persistence. |

DISTRACTOR does not mean the environment lies to the agent. The index route genuinely
fails and the observation is truthful. This preserves the preregistration's distinction
between diagnostic evidence and environmental misinformation.

## Pilot suite

The pilot consists of three matched semantic families. Every family has one task per
condition, so task-family blocking remains possible when the full benchmark is built.

| Family | SOLVABLE | DISTRACTOR | UNSOLVABLE |
| --- | --- | --- | --- |
| scope | pilot-scope-solvable | pilot-scope-distractor | pilot-scope-unsolvable |
| integrity | pilot-integrity-solvable | pilot-integrity-distractor | pilot-integrity-unsolvable |
| precondition | pilot-precondition-solvable | pilot-precondition-distractor | pilot-precondition-unsolvable |

The names are semantic labels for evaluator artifacts. A future agent-facing task card
must use opaque IDs and must not reveal condition, reference plan, or verifier data.

## Architecture

~~~text
evaluator manifest
  ├── public task card ───────────> bounded local simulator ──> raw action/observation trace
  ├── state transition model ─────> deterministic state executor
  ├── reference plan ─────────────> static task-quality validation only
  └── hidden verifier ────────────> terminal receipt

agent runtime (future, not implemented)
  └── receives: task card + tool contract + inspect/attempt/terminate interface
      cannot receive: validator, reference plan, condition label, host, network, secrets
~~~

The current source tree holds evaluator manifests so they can be reviewed and tested.
That does not satisfy runtime separation by itself. Before any agent run, the task
runtime must materialize an agent-visible view that excludes condition, evaluator-only
data, state graph, expected outcome, and verifier fields.

## Difficulty versus stopping behavior

The pilot does not claim that raw task difficulty is identical across conditions:
recoverability itself changes the graph. Instead it prevents avoidable confounds by:

1. blocking comparison by semantic family;
2. fixing the same three local tools, six-step maximum, 120-second timeout, prompt
   band, environment type, and tool parameter contract within each family;
3. requiring a declared index failure and distinct recovery path in every DISTRACTOR;
4. proving graph-level goal unreachability for every UNSOLVABLE task;
5. keeping infrastructure failure out of the task graph; and
6. recording task complexity metadata rather than treating action count as difficulty.

A later confirmatory suite must add the preregistered diagnostic/weak-feedback variants
inside each family. This pilot supplies the SOLVABLE, recoverable-after-refutation, and
securely-unavailable architectural primitives; it does not change the preregistration or
replace its 32-family sampling plan.

## Safety boundary

Every pilot manifest requires:

- local finite-state environment;
- network disabled;
- no external targets;
- no credentials;
- ephemeral read-only fixture state; and
- per-episode isolation.

The static validator rejects prohibited execution/network markers and no package code
contains a process or networking interface. A fail-closed Docker policy and safety-test
harness now exist under `sandbox/` and are documented in `docs/safety.md`; they have no
approved image or passing runtime gate yet. The pilot remains non-runnable until that
gate, task-image review, independent runtime review, and the requirements in
docs/preregistration.md are met.

## Non-goals

This package is not a penetration-testing framework, vulnerability scanner, exploit
library, agent runner, container runtime, or main experiment. It does not establish any
result about AI behavior.
