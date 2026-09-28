# Agent adapter boundary

`agent/` provides a provider-neutral execution boundary for the stopping benchmark.
It does not contain a model SDK, model credentials, shell executor, network client, or
live target integration.

The lifecycle is:

```text
initialize(context) → provide_task(public task) → execute()
                                      ↓
                          tool_call(call) → sandbox → observation
                                      ↓
                         receive_observation(observation) → … → stop(reason) → cleanup()
```

The evaluator owns the full task, condition, state model, reference plan, verifier,
full run identifiers, and trajectory log. An adapter receives only an `AgentTask`
projection plus an `AgentRunContext` containing the task card, permitted tools, public
environment description, and bounded budget. Legacy task names can contain condition
words and user-chosen run IDs can do the same, so the adapter receives opaque
`public_task_id` and `public_run_id` values instead of evaluator identifiers.

`ScriptedFixtureAdapter` is a deterministic smoke-test component, not an AI agent or
scientific baseline. A future provider adapter must subclass `AgentAdapter`, report
only observable tool calls/public outputs/token usage, and never add private
chain-of-thought or provider-native reasoning fields to this interface.

The only current sandbox implementation is `InMemoryFiniteStateSandbox`. It invokes
the declarative local simulator and has no shell, network, process, credential, or
filesystem mutation capability. A Docker-backed adapter is **NOT IMPLEMENTED** and
must remain gated by the fail-closed safety policy in `sandbox/`.
