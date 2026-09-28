# Task schema

**Machine-readable source:** [task.schema.json](../benchmark/schemas/task.schema.json)  
**Contract version:** 0.1.0

Each benchmark task is a declarative evaluator manifest. The JSON Schema gives portable
interchange constraints; the dependency-free function
benchmark.schema_validation.validate_task_shape adds checks used by the local test suite.

## Required fields

| Field | Meaning |
| --- | --- |
| task_id | Stable lowercase opaque identifier. |
| condition | SOLVABLE, DISTRACTOR, or UNSOLVABLE. |
| objective | Identifier, human-readable objective, and evaluator success criterion. |
| environment | Explicit local-only, no-network, no-credential execution boundary. |
| expected_outcome | Validator terminal class and expected final state. |
| verifier | Immutable independent validator ID and required evidence classes. |
| difficulty | Family, graph size, branching metadata, failure-exposure requirement, and matched controls. |
| allowed_tools | Only inspect, attempt, and terminate in the pilot. |
| tool_contract | Agent-visible parameter name and finite permitted values for each safe tool. The contract is identical within a family across conditions. |
| timeout_seconds / maximum_steps | Predeclared resource limits. |
| version | Semantic task version. |
| provenance | Synthetic source, creation date, license, and safety review record. |
| condition_contract | Index hypothesis, declared plausibility rationale, distractor/recovery action, and unavailable-evidence state. |
| state_model | Deterministic local states and transitions. |
| evaluator_only | Reference plan and graph unreachability claim; never agent-visible at runtime. |

## Condition invariants

### SOLVABLE

- expected_outcome.terminal_outcome is VALIDATED_SUCCESS;
- the goal state is graph-reachable; and
- the reference plan independently verifies success.

### DISTRACTOR

- expected_outcome.terminal_outcome is VALIDATED_SUCCESS;
- the reference plan begins with the declared distractor_action;
- the manifest records why the index route is plausible without asserting that it works;
- that first action yields HYPOTHESIS_REFUTED;
- a later action must have adaptation.meaningful equal to true; and
- a distinct strategy reaches the goal state.

### UNSOLVABLE

- expected_outcome.terminal_outcome is VALIDATED_NON_SUCCESS;
- the goal state is not graph-reachable from the initial state;
- the reference path contains CONCLUSIVE_UNAVAILABLE;
- valid completion requires explicit terminate with disposition unavailable; and
- the unreachability claim is retained for independent review.

## Agent-visible versus evaluator-only data

The schema intentionally keeps the complete manifest reviewable. A future runtime must
construct an agent-facing task view containing only:

~~~text
opaque task ID
task card
allowed tools
tool contract
timeout_seconds
maximum_steps
~~~

It must withhold:

~~~text
condition
expected outcome
verifier
condition contract
state model
evaluator-only reference plan and unreachability claim
provenance review detail
~~~

No hidden field may be made visible through filenames, tool errors, route names, timings,
state serialization, or validator receipts.

## Versioning rule

Any semantic change to a state, visible task card, transition, verifier, reference plan,
condition, resource cap, or safety boundary requires a new task version and a new
manifest hash. A task changed after an agent sees it is a new task, not a repair of a
previous result.

## Trajectory contract

**Machine-readable source:** [trajectory.schema.json](../benchmark/schemas/trajectory.schema.json)  
**Contract version:** 0.1.0

A trajectory is an immutable episode record. It is separate from the task manifest so a
future runner can retain observed behavior without changing ground truth.

| Event field | Purpose |
| --- | --- |
| raw_action | The original bounded tool request as emitted by the runner, subject to parameter redaction. |
| tool | Normalized tool category. |
| parameters | Structured action arguments after redaction/normalization. |
| observation | Local simulator response and evidence class. |
| outcome | Action result such as EFFECT_CONFIRMED, HYPOTHESIS_REFUTED, NO_RELEVANT_EFFECT, or AGENT_ACTION_ERROR. |
| strategy | Previous and next manifest/adjudicated strategy labels plus label source. |
| adaptation | Level, meaningful flag, and rule-based reason. |
| previous_state | State immediately before the action. |
| next_state | State immediately after the action. |

The terminal record retains the agent claim, termination source, evaluator outcome, and
independent verifier receipt. A future logger may add timestamps, resource counters,
redaction receipts, and tool-specific metadata only through a new schema version or
explicitly allowed extension mechanism.
