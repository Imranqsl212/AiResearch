# Archived protocol manuscript

Preserved on 2026-10-03 before the empirical paper revision. Historical status statements below are not current results.

# When Secure-Code Repair Fails

## Abstract

AI coding agents are increasingly asked to write and repair security-sensitive code,
but endpoint success does not reveal what they do after a checker rejects an attempt.
This protocol narrows that question to local application-level cryptographic misuse.
The proposed benchmark covers authenticated encryption, nonce handling, and key
management in disposable offline environments. For each family, matched tasks vary
feasibility (repairable versus securely unavailable) and feedback quality (diagnostic
versus weak but truthful), yielding four cells: RD, UD, RW, and UW. An evaluator-only
verifier checks cryptographic invariants and separates validated success from unsupported
success claims. Observable trajectories classify action changes, parameter mutations,
implementation changes, hypothesis changes, strategy changes, repetition, voluntary
stopping, budget stopping, timeout, and infrastructure failure. The study is designed
to test whether additional attempts represent genuine security-design adaptation or
surface-level persistence. No provider-backed pilot or main experiment has yet been
run, so this manuscript reports a protocol and implementation status rather than
empirical findings.

## 1. Introduction

Security-sensitive code is a useful stress test for tool-using agents because plausible
code can compile and pass shallow tests while violating a cryptographic invariant.
Success rate alone cannot show whether an agent understood checker feedback, changed
the security design, repeated a disproven hypothesis, or claimed success prematurely.
A controlled post-failure trace is therefore the scientific object.

The project asks a narrow question rather than making a claim about cybersecurity in
general: after an independent checker rejects a cryptographic implementation, does an
agent repair the underlying design, keep mutating parameters, or stop when the local
evidence supports stopping? The contribution is a matched, verifier-backed local
benchmark and an analysis plan that treats actions as events nested within task
families.

## 2. Related Work

ReAct, Reflexion, and Self-Refine show how observations and feedback can support
iterative revision. Recovery and abstention benchmarks show that agents can be tested
on backup paths and unavailable goals. Cyber and software-engineering benchmarks show
the value of executable environments and state-based verification. Cryptographic
standards and guidance define the security invariants used here: authenticated
encryption, nonce uniqueness, and safe key handling.

Existing work measures pieces of this problem—eventual success, recovery, abstention,
or crypto misuse—but does not by itself provide the proposed combination of matched
feasibility/feedback cells, crypto-specific strategy coding, independent receipts, and
unsupported-success measurement. This is a bounded positioning claim, not a claim
that post-failure behavior is unstudied.

## 3. Research Questions

RQ1 asks whether a post-failure strategy transition is outcome-changing when repair is
possible and whether the agent stops or hands off when no route exists. RQ2 compares
feasibility and feedback diagnosticity. RQ3 describes evidence preceding stopping
classes. RQ4 separates surface action changes from genuine crypto-design changes. RQ5
measures unsupported success claims.

The preregistered hypotheses predict neither success nor failure. They test reduced
same-hypothesis repetition under diagnostic feedback, more validated strategy changes
on repairable tasks, a gap between action and strategy diversity, excessive persistence
on unavailable tasks, and a non-zero unsupported-claim rate.

## 4. Methodology

The active benchmark is version 0.3.0. It has three families:

- aead: confidentiality and ciphertext integrity;
- nonce: nonce uniqueness for each key;
- key-management: no hardcoded key or unsafe fallback.

Each family contains RD (repairable/diagnostic), UD (unavailable/diagnostic), RW
(repairable/weak truthful), and UW (unavailable/weak truthful). The agent sees only a
bounded task card and local tools. It does not see condition labels, hidden state,
reference plans, verifier code, credentials, or host paths.

A trajectory contains observable actions, parameters, tool observations, checker
feedback, outcomes, budget, timestamps, explicit terminal claims, and evaluator
receipts. It contains no private chain-of-thought. A parameter mutation keeps the same
security design; a strategy change adopts a different design or security hypothesis.
Different syntax is not sufficient.

The verifier executes against the actual local artifact, checks positive and negative
cases plus regression behavior, and emits a hash-linked receipt. The evaluator—not
the agent—assigns terminal outcome. The planned terminal classes are validated
success, validated non-success, unsupported success, voluntary stop, budget stop,
timeout, infrastructure failure, and invalid task.

## 5. Experimental Setup

The target will run in a Docker Desktop environment with no public egress, no host
filesystem mounts, no credentials, bounded CPU/memory/process resources, and disposable
state. The agent adapter will isolate benchmark logic from provider-specific execution.
The provider, model ID, prompt, agent version, image digest, verifier version, budget,
and Git commit will be frozen before collection.

The development suite has 12 tasks. The planned main study contains approximately
30–40 quality-approved tasks with at least three runs per task, and up to five if
resources permit. Exact tasks and repeats will be recorded in a final manifest. The
primary inferential unit is the task family; runs are nested, and actions are not
independent samples.

## 6. Results

No provider-backed smoke test, pilot, or main experiment has been completed in this
crypto scope. The repository currently contains the declarative benchmark, static
quality checks, protocol, and Docker Desktop safety implementation. Therefore no
empirical success rate, stopping rate, or hypothesis result is reported here.

## 7. Qualitative Analysis

After quantitative freeze, a predeclared stratified sample of approximately 20–30
complete trajectories will be coded by blinded reviewers where possible. Categories
are repetition, parameter-only mutation, implementation change, hypothesis change,
strategy adaptation, evidence-supported stop, excessive persistence, and unsupported
success. Disagreements will be adjudicated and agreement reported.

## 8. Discussion

If the study is run, data will be separated from interpretation and non-conclusions.
A result can support a claim about the tested configuration and local crypto tasks; it
cannot establish how all AI agents behave or how an agent reasons privately. Difficulty,
feedback wording, budget, tool interface, verifier error, and provider stochasticity
are explicit alternative explanations.

## 9. Limitations

The first study may use one provider-backed agent, a small synthetic benchmark, a
limited number of task families, repeated runs, and a checker-specific definition of
security. Crypto repair may measure API knowledge rather than general reasoning.
Docker containment and executable verifier correctness require runtime validation.
Small cluster counts limit statistical power, and qualitative labels require agreement
checks. These limitations are not evidence for or against the hypotheses.

## 10. Safety and Ethics

All tasks are local and intentionally bounded. No real target, public IP, production
credential, SSH key, cloud secret, or live exploit is used. The verifier is outside
the agent workspace, Docker safety checks fail closed, resources are capped, and each
run is disposable. Any release must exclude secrets, host paths, private provider
data, and capabilities that could contact external systems.

## 11. Conclusion

This project reframes the broad stopping question as a measurable cryptographic repair
study. Its central test is whether observable post-failure behavior reflects a change
in security design and evidence-sensitive stopping, rather than merely more tool calls.
The protocol remains provisional until the executable target, provider adapter, smoke
test, pilot, and frozen main experiment pass their gates.

## 12. References

- NIST. Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode
  (GCM) and GMAC, SP 800-38D.
  https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38d.pdf
- IETF. RFC 5116: An Interface and Algorithms for Authenticated Encryption.
  https://www.rfc-editor.org/rfc/rfc5116
- IETF. RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3.
  https://www.rfc-editor.org/rfc/rfc8446
- OWASP. Cryptographic Storage Cheat Sheet.
  https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- Yao et al. ReAct: Synergizing Reasoning and Acting in Language Models.
  https://arxiv.org/abs/2210.03629
- Shinn et al. Reflexion: Language Agents with Verbal Reinforcement Learning.
  https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html
