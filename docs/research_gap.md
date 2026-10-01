# Research gap: post-failure adaptation in cryptographic repair

## Narrowed problem

The project does not claim that agents have never been studied after failure. Agent
recovery, abstention, self-correction, process evaluation, false-success detection,
and cyber benchmarks already cover important parts of that space. The question is
narrower:

> After an independent checker reports that a cryptographic implementation is not
> secure, does an agent change the security design, merely mutate surface parameters,
> or continue without a valid path—and does it stop only when the evidence supports
> stopping?

The first domain is local application-level cryptographic misuse involving
authenticated encryption: AEAD use, nonce handling, and key management.

## What existing work measures

| Existing line | What it establishes | What it does not isolate here |
| --- | --- | --- |
| ReAct, Reflexion, Self-Refine | Tool feedback can support iterative revision. | Whether a cryptographic failure causes a validated strategy change rather than another edit. |
| Agent recovery and abstention benchmarks | Agents can be tested on backup paths, unavailable tasks, and act/abstain decisions. | Crypto-specific invariant repair with a trace taxonomy separating parameter edits from design changes. |
| Crypto misuse research and API guidance | Unsafe API patterns and secure invariants can be specified. | Post-feedback behavior, stopping, and unsupported success claims of a tool-using agent. |
| Cyber/code benchmarks | Endpoint success and patch quality can be evaluated in sandboxed environments. | A matched repairable/unavailable design with diagnostic versus weak truthful feedback. |
| State-based verification work | Natural-language completion claims are weaker than independent state checks. | A crypto-repair trajectory measure linking claims, evidence, and stopping events. |

## Proposed contribution (Z)

The study proposes a controlled, local measurement layer with four matched cells per
crypto family:

1. `RD`: repairable with diagnostic feedback;
2. `UD`: unavailable with diagnostic feedback;
3. `RW`: repairable with weak but truthful feedback;
4. `UW`: unavailable with weak but truthful feedback.

The outcome is not just success. The trace records whether the agent repeats a
hypothesis, mutates a relevant parameter, changes implementation, changes hypothesis,
changes security strategy, stops voluntarily, stops because of budget/timeout, or
claims success without an independent cryptographic receipt.

## Alternative explanations for novelty

1. **Generic self-correction may already answer the question.** If prior agents
   already record edits after failed tests, this project would add value only if the
   crypto-specific invariant and strategy codebook reveal behavior that generic pass
   rates hide.
2. **Crypto tasks may be API memorization, not reasoning.** The result could reflect
   whether a model remembers AEAD/nonce rules. We therefore need matched families,
   diagnosticity controls, negative cases, and a separate analysis of design-level
   changes—not claim general cyber reasoning.
3. **Feedback wording or task difficulty may explain the effect.** The four-cell
   design controls feedback diagnosticity and feasibility within family, while public
   task cards, budgets, and tools remain matched. Residual difficulty remains a
   limitation and must be measured.
4. **Verifier artifacts may create false labels.** Independent executable checks,
   alternate-route validation, receipt hashes, and invalid-task exclusions are needed
   before interpretation.
5. **Budget may explain stopping.** Voluntary stop, budget stop, timeout, tool error,
   and infrastructure abort are separate terminal classes; stopping analyses must
   condition on remaining budget.

## Does the gap survive?

Conditionally, yes. The broad claim does not survive. A defensible claim is that the
study combines a cryptographic misuse domain, matched feasibility/feedback cells,
independent executable verification, and an observable adaptation taxonomy. The gap
survives only if the final implementation demonstrates that task difficulty, checker
errors, interface cues, and forced termination do not fully explain the observed
contrasts. Until then, this is a proposed gap, not an established finding.
