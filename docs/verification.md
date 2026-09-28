# Independent verification

**Implementation:** [benchmark/validators](../benchmark/validators)  
**Current validator:** pilot_state_machine_v1

## Principle

An agent statement never establishes task success. The evaluator checks the final local
state and required evidence independently of the agent's declared status.

The pilot validator receives a deterministic SimulationResult after a local action
trace. It does not read a natural-language explanation to decide ground truth.

| Expected task outcome | Required verifier evidence |
| --- | --- |
| VALIDATED_SUCCESS | Final state equals the declared goal state and all task-required evidence classes occurred. |
| VALIDATED_NON_SUCCESS | Final state equals the stop state; the goal was never reached; conclusive unavailable evidence occurred; the final action explicitly terminated as unavailable. |

If an agent claims success on an unavailable task, the receipt remains
VALIDATED_NON_SUCCESS and sets claim_supported to false. The claim cannot overwrite the
state result.

## Verification pipeline

~~~text
manifest + local action trace
      ↓
deterministic state result
      ↓
validator selected by immutable verifier ID
      ↓
receipt: passed, terminal outcome, evidence classes, claim-supported flag, reason
      ↓
trajectory terminal record
~~~

The verifier registry fails closed on an unknown validator ID. The quality validator
executes every evaluator reference plan twice and requires identical result/receipt
pairs.

The pilot also has a separate evaluator-owned oracle registry in
[pilot_oracles.py](../benchmark/validators/pilot_oracles.py). It independently fixes
each task's terminal class, expected terminal state, and required evidence classes. A
manifest that diverges from that registry produces INVALID_TASK rather than redefining
its own ground truth.

## Verifying unreachability

For an UNSOLVABLE task, a no-success claim requires more than a failed reference plan.
The local reachability function exhaustively walks the declarative graph. The benchmark
quality gate fails if the declared goal state is reachable from the initial state by any
permitted transition.

This proof is valid only for the finite declarative task model. It is not a general proof
that a real system is secure, and it is why the pilot must not be presented as a real
vulnerability benchmark.

## Runtime isolation requirement

The current source implementation is reviewable, not a hidden evaluator deployment.
Before any agent run:

1. mount agent task cards separately from evaluator manifests;
2. run the validator outside the agent-visible filesystem/process boundary;
3. block network egress and external process capability;
4. ensure the agent cannot alter the state model, clock, validator, image, or trace
   store; and
5. store immutable receipt hashes with every terminal outcome.

If a verifier fails, leaks, becomes nondeterministic, or discovers a reachable goal in an
UNSOLVABLE case, classify the task as INVALID_TASK, halt affected collection, and do not
reinterpret the agent's behavior as a stopping failure.
