# Benchmark design: cryptographic repair after failed feedback

**Active version:** `0.3.0`
**State:** 12 declarative development tasks; executable Docker target and agent runs
are **NOT IMPLEMENTED**.

## Scope

The first study is intentionally narrow: application-level cryptographic misuse in
authenticated encryption. Tasks use bounded local interfaces and disposable code
artifacts. They do not ask an agent to invent cryptographic primitives, contact a
real service, exploit a public target, or handle real credentials.

## Matched design

Each family has the same public task card, initial plausible route, tool contract,
timeout, step budget, and visible feedback format. The hidden factors are feasibility
and feedback diagnosticity:

| Cell | Feasibility | Feedback | Expected endpoint |
| --- | --- | --- | --- |
| RD | repairable | diagnostic and truthful | repair or evidence-based continuation |
| UD | securely unavailable | diagnostic and truthful | justified non-success/stop |
| RW | repairable | weak but truthful | recovery requires more diagnosis |
| UW | securely unavailable | weak but truthful | no valid repair path |

The active families are:

| Family | Security invariant |
| --- | --- |
| `aead` | confidentiality and ciphertext integrity are both enforced |
| `nonce` | nonce uniqueness is preserved for each key |
| `key-management` | no hardcoded key or unsafe fallback; approved key interface is used |

The task card never reveals the cell label, hidden oracle, reference route, or
verifier implementation. A distractor is represented by a plausible but irrelevant
repair hypothesis, not by false checker output.

## What the static benchmark proves

`python3 -m benchmark.quality_four_cell --json` checks schema validity, one task per
cell and family, deterministic reference execution, graph consistency, and receipt
semantics. It does not prove that a Docker target is isolated or that a provider
agent can solve a task. Those are independent readiness gates.

## Executable target requirements

Before any smoke test, each task must be materialized in a local target image and
checked by an evaluator-only verifier. The verifier must test the actual artifact,
negative cases, regression behavior, and the family invariant. At least two legitimate
routes must be tested where the task claims recoverability; unreachability must be
checked by an independent alternate-route audit.

## Legacy material

The original generic `SOLVABLE`/`DISTRACTOR`/`UNSOLVABLE` nine-task pilot is retained
under legacy paths for auditability. It is not evidence for the crypto study and is not
included in the active sample or paper results.

## Safety boundary

The only permitted target is a local disposable container with no external network,
host mounts, credentials, SSH keys, or cloud secrets. The evaluator and raw archive
remain outside the agent-visible workspace. A failed safety gate blocks execution.
