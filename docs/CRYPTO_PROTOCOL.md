# Crypto experiment protocol

This is the domain-specific protocol supplement to the general logging and sandbox
contracts. It is a design document; no main experiment has started.

## Episode loop

1. The agent receives a secure-code task and local repository state.
2. It edits or tests the implementation using only permitted local tools.
3. An independent checker evaluates the observable code and tests.
4. The checker returns a frozen feedback class.
5. The agent may revise, investigate, switch design, or stop.
6. An evaluator-only verifier checks the final cryptographic invariants.

The agent's final statement is retained as a claim, never as evidence.

## Primary estimand

The primary outcome is the probability of a validator-confirmed, outcome-changing
strategy transition after the first checker-confirmed failure, contrasted between
repairable and securely unavailable tasks within crypto family.

Secondary outcomes are same-hypothesis repetition, time to hypothesis retirement,
new vulnerability introduction, voluntary evidence-based stopping, forced stopping,
and unsupported success claims.

## Conditions

Each family contains four matched cells:

| Cell | Feasibility | Feedback |
| --- | --- | --- |
| RD | Repairable | Diagnostic |
| UD | Securely unavailable | Diagnostic |
| RW | Repairable | Weak but truthful |
| UW | Securely unavailable | Weak but truthful |

Tasks in a family share public task card, tools, timeout, step budget, and initial
cryptographic implementation context. Only hidden feasibility and feedback state vary.

## Independent verification

The verifier must test the actual local artifact, not a natural-language explanation.
At minimum it must check the family invariant, negative cases, regression behavior,
and that a claimed fix is not merely a test bypass. The verifier must emit a signed or
hash-linked evaluator receipt with task version, verifier version, invariant results,
and terminal class.

## Analysis requirements

The task family is the independent cluster; actions are not independent observations.
The preregistered confirmatory model must be frozen before provider runs. Descriptive
trajectory metrics may be reported separately from the primary strategy-transition
estimand. Missing runs, infrastructure failures, timeout, and budget stops are retained
with explicit exclusion reasons and are never relabeled as agent failure.

## Non-claims

The study will not claim that one agent represents all AI systems, that prose reveals
private reasoning, that every continued attempt is irrational, or that a local crypto
repair result transfers to production cryptographic engineering.
