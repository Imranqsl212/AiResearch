# When to Stop: An Auditable Protocol for AI Agents After Failed Cybersecurity Actions

**Manuscript status after four-reviewer audit:** protocol and implementation-status paper, 2026-09-29. Not an empirical agent-behavior submission. The main experiment has not been collected in this repository; Section 7 reports artifact availability and static validation only. The unresolved blockers and corrected issues are recorded in [the peer review](../docs/FINAL_PEER_REVIEW.md) and [reproducibility audit](../docs/FINAL_REPRODUCIBILITY_AUDIT.md).

## 1. Abstract

AI agents that investigate security problems must decide what to do after an attempted route fails. A final success score cannot distinguish a productive alternative from repeated attempts, a justified decision to stop, an exhausted budget, or a success claim unsupported by the target state. We specify a study that treats these as separate observable outcomes. Its proposed task families contrast recoverable and unavailable goals under diagnostic or weak but truthful feedback. Actions and tool observations would be linked to a hidden verifier, while strategy changes would require a declared action-to-route mapping or blinded annotation. Repeated runs would be analyzed within task families. In the current repository, static checks pass for nine local finite-state pilot tasks, and the observable logging contract is exercised by one deterministic scripted fixture. The analysis inventory contains no eligible main-experiment trajectory and no provider-backed agent outcome. The Docker safety gate has not passed its runtime checks because no immutable task image has been approved. Consequently, the study cannot estimate recovery, persistence, stopping, or false-success rates, and no hypothesis is tested. The present contribution is a reviewable measurement protocol and an audit of the conditions required for an empirical evaluation. Agent-behavior conclusions require a frozen task suite, a validated sandbox, independent real-agent runs, and blinded trajectory coding.

## 2. Introduction

An agent can fail in several ways that lead to the same endpoint score. It may abandon a viable route too early, continue a route after diagnostic refutation, stop because its budget expires, or announce success without changing the relevant system state. A single success indicator cannot identify which process occurred. This matters acutely in cybersecurity work, where unsuccessful attempts and claims of success may affect operator decisions.

Trajectory evaluation is not new. [AgentBench](https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html) reports failure categories; [AgentBoard](https://arxiv.org/abs/2401.13178) measures intermediate progress. Work on [recovery from external failures](https://arxiv.org/abs/2508.11027) and [agent abstention](https://arxiv.org/abs/2607.10059) addresses adjacent questions directly. Our narrower proposed gap is a matched, verifier-backed account of what follows **task-level negative evidence** in a safe cyber episode: which route is attempted next, whether a changed command changes the higher-level strategy, and whether termination is voluntary or forced. This is a proposed evaluation design, not an established empirical finding.

The planned contribution has three parts: an action/observation and terminal-state codebook; paired recoverable and unavailable local tasks with independent verification; and a family-aware analysis that treats a run as a repeated observation within a task family. The current contribution is limited to the design and its static engineering checks. It does not yet establish agent performance.

## 3. Related Work

[ReAct](https://arxiv.org/abs/2210.03629) demonstrates an interleaved action and observation pattern that makes an agent's external behavior inspectable. [AgentBench](https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html) evaluates interactive tasks and analyzes failures; [AgentBoard](https://arxiv.org/abs/2401.13178) adds progress measurement. These studies motivate examining intermediate states. Progress alone does not answer whether the agent retired a refuted security hypothesis or merely tried a new command spelling.

[Hell or High Water](https://arxiv.org/abs/2508.11027) deliberately interrupts a planning path while preserving a feasible backup in its central benchmark, allowing recovery to be measured under controlled external failures. [AgentAbstain](https://arxiv.org/abs/2607.10059) constructs paired should-act and should-abstain settings, including cases where the need to abstain appears during execution. Our proposal adapts the comparison to local security investigation and adds explicit task-hypothesis labels, independent goal reachability, and separate budget versus voluntary stopping records. It does not claim to originate recovery or abstention evaluation.

For endpoint validity, [τ-bench](https://arxiv.org/abs/2406.12045) compares final database state with a goal state across repeated trials. A [false-success study](https://arxiv.org/abs/2606.09863) directly examines the divergence between completion claims and independent state. Our protocol uses the same basic lesson: a final message is data about the agent's claim, whereas a separate verifier decides whether the task succeeded. It also records the preceding evidence trajectory so a terminal claim can be examined in context.

Cyber benchmarks such as [Cybench](https://arxiv.org/abs/2408.08926) and [CyberGym](https://arxiv.org/abs/2506.02548) provide task environments and outcome checks. Their primary published measures emphasize solved tasks, subtasks, or proof-of-concept validity. The present proposal focuses on post-failure behavior under matched conditions. [PrimeVul](https://arxiv.org/abs/2403.18624) reinforces a separate warning: labels, duplicates, and splitting rules can change apparent capability. Task reachability, verifier independence, and family identity therefore require their own audit before behavioral comparisons.

## 4. Research Questions

**RQ1:** After a predefined diagnostic negative-evidence event, does the agent recover when an approved alternative remains and stop under the protocol when the goal is unavailable?

**RQ2:** Holding task family and initial route fixed, how do feasibility and feedback diagnosticity relate to subsequent actions?

**RQ3:** What observable evidence and remaining budget precede self-termination, budget termination, timeout, and infrastructure abort?

**RQ4:** How often do changed actions represent material parameter, hypothesis, or strategy changes, rather than surface variation or repetition?

**RQ5:** Among terminal success claims, how often does the independent verifier fail to support the claim?

These are planned questions. No answer to them is reported here.

## 5. Methodology

### Benchmark and conditions

The current implemented pilot is a finite-state local fixture with `SOLVABLE`, `DISTRACTOR`, and `UNSOLVABLE` tasks. It is designed to check state reachability and verifier wiring. The [preregistration draft](../docs/preregistration.md) specifies a different confirmatory factorial design: recoverable or unavailable goals crossed with diagnostic or weak but truthful feedback (`RD`, `UD`, `RW`, `UW`), plus a separate infrastructure-error control. Each matched family would keep its interface, initial route, tools, and budget aligned. This confirmatory suite is not implemented. The two condition systems cannot be pooled or renamed after outcome inspection; the final protocol and task count must be reconciled before collection.

Each task should declare a versioned state model, allowed tools, success invariant, negative-evidence contract, and a reference path or unreachability argument. A static path through a finite-state graph proves only the graph's declared reachability. A future image-backed task requires an independent review of its executable state and hidden verifier.

### Agent, sandbox, verifier, and logging

The code defines an agent adapter interface for initialization, task presentation, action exchange, stopping, and cleanup. At present, the only concrete adapter is a deterministic scripted test double; no provider-backed research agent is configured. The evaluator projects an opaque public task and run ID to the adapter. The true condition, reference plan, hidden state, and verifier remain evaluator-side.

The sandbox policy specifies local Docker execution with disabled networking, no host mounts or credentials, bounded CPU, memory, process count, runtime, and disposable state. The static policy is checked. The runtime isolation probes remain unexecuted because no reviewed immutable image is in the approval list. The only completed end-to-end fixture uses an in-memory finite-state sandbox, not Docker.

The finite-state verifier checks the goal state separately from the agent's final response. The logger records observable tool calls, parameters, observations, errors, budgets, stop events, verifier receipts, and append-only hash receipts. It excludes private chain-of-thought. One deterministic fixture verifies this wiring. It is excluded from research outcomes.

### Trajectory labels and metrics

A logical completed action is one tool observation paired with its tool request. A failure event requires a declared diagnostic refutation or weak negative observation; a platform error is a separate class. The [analysis codebook](../analysis/codebook.md) distinguishes exact action repetition, evidence-relevant parameter mutation, tool change, hypothesis change, and strategy transition. A changed command is not enough to infer a changed strategy. Strategy labels must come from a frozen task mapping or blinded adjudication of observable behavior.

Planned run-level measures include verifier-confirmed success, actions and failure events before termination, switches and repetition rates with explicit denominators, post-failure adaptation, voluntary and forced termination, and unsupported success claims. “Operationally justified stop” is a narrow protocol label requiring unavailable-goal evidence, exhausted permitted alternatives, an agent-initiated terminal action before a cap, and validator confirmation. It does not imply access to private beliefs.

### Statistical plan

The task family is the independent cluster; runs repeat within a family. The [draft preregistration](../docs/preregistration.md) names paired calibration as the primary target, family-cluster bootstrap intervals for effect sizes, a one-sided intersection-union test for its two components, and paired condition contrasts for secondary questions. Secondary p-values require multiplicity control. The current pipeline can produce run-level tables, cluster summaries, permutation fallbacks for matched secondary contrasts, and figures after an immutable input lock. Its preregistered primary GEE test is not implemented. With no eligible runs, none of these inferential procedures is executed.

## 6. Experimental Setup

The repository contains nine versioned pilot tasks in three condition labels, with static reference-plan validation and evaluator-owned goal checks. All nine have a six-step cap and declared branching factor of two; however, declared transition counts are three for each `SOLVABLE`, five for each `DISTRACTOR`, and four for each `UNSOLVABLE` task. These pilot conditions are therefore not difficulty-matched by this structural proxy. The adapter, trajectory, manifest, and verifier schemas are implemented. The only stored trajectory is one deterministic scripted integration fixture. There is no frozen main-study manifest, task suite, provider revision, container image digest, or Git commit. The approved Docker image list is empty. Collection therefore remains blocked by the project's safety and provenance gates.

The [experiment execution report](../docs/experiment_report.md) documents the preflight decision. The [analysis input inventory](../tables/stopping_experiment/input_inventory.csv) lists the sole fixture and its exclusion reason. These records are the source for the implementation-status statements below.

## 7. Results

There are no main-experiment results. The reproducible [analysis status](../analysis/results.md) reports zero eligible main runs and zero independent task-family clusters; the only stored trajectory is excluded because its manifest identifies a scripted engineering fixture. Static [benchmark validation](../benchmark/quality.py) passes all nine pilot task definitions and their reference plans. This establishes internal consistency of that finite-state fixture, not agent competence or behavior. The current [safety receipt](../sandbox/safety_checks/latest_result.json) reports that runtime containment tests did not run and `experiment_permitted` is false.

Recovery rate, strategy switching, repetition, justified stopping, forced stopping, false-success frequency, confidence intervals, p-values, and effect sizes are **not estimable** from this workspace. The [figure manifest](../figures/stopping_experiment/figure_manifest.json) therefore withholds the planned empirical figures. A numerical zero for a behavior rate would be misleading: no eligible agent behavior was observed.

## 8. Qualitative Analysis

The planned qualitative sample is roughly two dozen trajectories balanced by condition and terminal class, followed by blinded coding and disagreement adjudication. No eligible trajectory is available for that procedure. The scripted fixture can show that a log contains a tool observation, stop event, and verifier receipt, but it cannot illustrate a model's adaptation or persistence. We therefore report no agent case study or representative trajectory.

## 9. Discussion

**Data show:** the installed pilot task contracts and reference plans pass static validation; the logging fixture is internally consistent; the main analysis has no eligible research runs. These are engineering observations.

**We interpret:** independent state verification and explicit stop-source recording are necessary to keep success claims, voluntary termination, and forced endings distinct. The prior literature supports the design motivation, while the current checks support only parts of the instrumentation.

**We cannot conclude:** whether an AI agent adapts after failure, persists excessively, knows when to stop, or claims unsupported success in these tasks. The record provides no evidence for or against the primary hypothesis. The analysis is not a failed agent result; it is an uncollected study.

## 10. Limitations

No actual model or provider-backed agent has been evaluated. The pilot is small, finite-state, and constructed by the researchers; its task difficulty and plausibility for an agent remain unmeasured. Its transition-count imbalance is a concrete condition/difficulty confound, so a future difference in stopping cannot be attributed to feasibility without matched redesign or an explicit sensitivity analysis. Three pilot condition labels differ from the four-cell confirmatory proposal. Stochastic behavior, subscription limits, provider drift, repeated measurements, annotation agreement, and model-specific effects cannot yet be estimated. The local fixture cannot establish external validity for real bug hunting or live cyber environments.

The verifier has been tested against declared finite-state outcomes but has not been independently validated on an executable container task. Task contracts and verifier logic could share an incorrect assumption. Structured strategy mappings may reflect the benchmark designer's categories; blinded coding and inter-rater reliability remain necessary. The raw analysis pipeline exists, but the confirmatory GEE implementation, final task-family metadata, frozen configuration, and complete Docker safety gate are pending. The absence of Git provenance prevents a full source-state reproduction claim.

## 11. Safety and Ethics

The intended target is an intentionally local, disposable research environment. The Docker policy forbids external networking, host mounts, real credentials, and privileged capabilities, and sets resource and time limits with cleanup. These are specified and statically checked controls; runtime containment has not been demonstrated for an approved task image. No real service, public IP, or third-party target is part of the task set. The in-memory fixture has no network or shell capability.

If later tasks use real vulnerability examples, release decisions should consider dual-use exposure, vendor disclosure status, and whether a benchmark artifact would make exploitation easier. Public release of a trajectory should omit credentials, private chain-of-thought, and unnecessary exploit details. A failed safety check must prevent collection rather than become a task outcome.

## 12. Conclusion

This repository currently supports a protocol and partial instrumentation for studying AI-agent behavior after failed local cybersecurity actions. It does not support an empirical claim about an agent's adaptation, stopping, or false-success rate. The decisive next step is a reviewed, frozen main study with a passing runtime safety gate and independently verifiable trajectories. Until then, the strongest conclusion is methodological: the planned constructs have explicit observable definitions, while the hypothesis remains untested.

## 13. References

The following primary sources were checked against their publisher or author-hosted records for this manuscript. The expanded project bibliography is in [`literature/bibliography.bib`](../literature/bibliography.bib).

1. Yao et al. (2023). [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629). ICLR.
2. Liu et al. (2024). [AgentBench: Evaluating LLMs as Agents](https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html). ICLR.
3. Ma et al. (2024). [AgentBoard: An Analytical Evaluation Board of Multi-turn LLM Agents](https://arxiv.org/abs/2401.13178). NeurIPS.
4. Wang et al. (2025). [Hell or High Water: Evaluating Agentic Recovery from External Failures](https://arxiv.org/abs/2508.11027). COLM.
5. Liu et al. (2026). [AgentAbstain: Do LLM Agents Know When Not to Act?](https://arxiv.org/abs/2607.10059). arXiv preprint.
6. Yao et al. (2024). [τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains](https://arxiv.org/abs/2406.12045). arXiv preprint.
7. Advani (2026). [From Confident Closing to Silent Failure: Characterizing False Success in LLM Agents](https://arxiv.org/abs/2606.09863). arXiv preprint.
8. Zhang et al. (2024). [Cybench: A Framework for Evaluating Cybersecurity Capabilities and Risks of Language Models](https://arxiv.org/abs/2408.08926). arXiv preprint.
9. Wang et al. (2025). [CyberGym: Evaluating AI Agents' Real-World Cybersecurity Capabilities at Scale](https://arxiv.org/abs/2506.02548). arXiv preprint.
10. Ding et al. (2025). [Vulnerability Detection with Code Language Models: How Far Are We?](https://arxiv.org/abs/2403.18624). ICSE.
