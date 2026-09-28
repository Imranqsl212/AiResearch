# Benchmark quality gates

**Scope:** the nine-task local pilot, not the main experiment.

## Automated checks

Run:

~~~sh
python3 -m benchmark.quality --json
~~~

The command is a static evaluator check with agent_runs_launched equal to zero. It
validates:

| Gate | What fails it |
| --- | --- |
| Manifest shape | Missing required fields, invalid condition, unsafe tool name, malformed task metadata. |
| Local safety | Network, external-target, credential, filesystem, or execution-marker violation. |
| State graph | Unknown states, duplicate transitions, undeclared tool, graph/count mismatch. |
| Independent verification | Reference plan rejected by the validator or expected state/outcome mismatch. |
| Determinism | Two reference executions yield different result/receipt records. |
| SOLVABLE correctness | No graph path to the goal state. |
| DISTRACTOR correctness | No declared refuted index path, no meaningful adaptation, or no strategy shift to success. |
| UNSOLVABLE correctness | Any permitted path reaches the goal, unavailable evidence is absent, or explicit stop fails. |
| Suite balance | Not exactly 3 tasks in each condition or not exactly one of each condition per family. |

## Quality principles

1. **No infrastructure-as-ground-truth.** The task model has no network/process
   dependency, so an unavailable result cannot be caused by a service outage.
2. **No self-certification.** The verifier checks state, not an agent claim.
3. **No silent repair.** A task whose oracle/graph is invalid is removed from a
   confirmatory denominator and kept in an invalidation ledger.
4. **Family blocking.** Scope, integrity, and precondition tasks are organized as
   semantic blocks, not nine independent observations.
5. **No raw action pseudoreplication.** Events create trajectory labels; future analysis
   clusters outcomes by task family.
6. **No hidden condition leakage.** The future agent-facing view excludes evaluator-only
   fields and condition labels.

## Pilot limitations

The finite-state design correctly tests architecture, trace semantics, verifier
separation, and unreachability proof mechanics. It does **not** test:

- an agent runner or model integration;
- container isolation or true egress enforcement;
- language/runtime failures;
- real-code vulnerability discovery;
- task difficulty equivalence beyond declared matched controls;
- annotation agreement; or
- the preregistered 32-family statistical study.

Those remain freeze gates in [preregistration.md](preregistration.md). The pilot must
pass independent task/validator review before it becomes a development fixture for the
larger benchmark.

