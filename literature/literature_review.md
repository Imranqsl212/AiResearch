# Literature review: *When to Stop*

**Project:** *When to Stop: How AI Agents Adapt After Failed Attacks and Why They Fail to Give Up*  
**Review snapshot:** 2026-09-28  
**Status:** literature and design review only. No main experiment was started.

## Scope and source discipline

This review asks a deliberately narrower question than “can agents succeed at cyber tasks?”: after an agent receives evidence against an attack hypothesis, how can a study tell productive recovery apart from redundant persistence, a justified stop, a forced timeout, and an unsupported claim of success?

The accompanying [matrix](literature_matrix.csv) contains 33 individually documented records, and the [bibliography](bibliography.bib) retains primary-source URLs. Conference proceedings and official publisher pages are preferred. Current arXiv records and technical reports are included where they are directly relevant, but are marked as preprints or reports rather than treated as settled, peer-reviewed evidence. The 2026 incident material is used only at a high level; it is not a source of attack procedures and does not provide the causal ground truth for this project.

The review covers agent architectures, self-correction, recovery, abstention, verification, cyber-agent benchmarks, vulnerability datasets, benchmark integrity, reward hacking, incident analysis, and bounded-rationality theory. It does not claim an exhaustive survey of all agent work.

## Executive synthesis

Five conclusions are already well supported by the reviewed literature.

1. **Outcome-only evaluation is insufficient, but it is not the only alternative.** [AgentBoard](https://arxiv.org/abs/2401.13178) tracks intermediate progress, [AgentBench](https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html) categorizes failures, and [AutoPenBench](https://aclanthology.org/2025.emnlp-industry.114/) uses vulnerability-testing milestones. A new study cannot claim to be the first to inspect an agent trajectory.

2. **Recovery and abstention are already direct empirical topics.** [Hell or High Water](https://arxiv.org/abs/2508.11027) injects external tool failures while preserving backup plans and also tests settings with no feasible solution. [AgentAbstain](https://arxiv.org/abs/2607.10059) builds paired should-act/should-abstain tasks, including runtime-discovered triggers. Therefore, “agents fail to stop” is not an untouched research topic.

3. **A terminal statement is not a valid outcome label.** [τ-bench](https://arxiv.org/abs/2406.12045) and [AppWorld](https://arxiv.org/abs/2407.18901) use environment-state checks. A recent preprint on [false success](https://arxiv.org/abs/2606.09863) reports that natural-language completion claims can diverge substantially from independent environment state in its studied datasets. [Evidence-Carrying Termination](https://arxiv.org/abs/2608.23623) proposes a certificate gate for the terminal boundary. The project therefore needs a deterministic validator and must report unsupported success separately.

4. **Cyber-agent benchmarks are increasingly realistic but primarily outcome-oriented.** [Cybench](https://arxiv.org/abs/2408.08926), [CVE-Bench](https://arxiv.org/abs/2503.17332), [CyberGym](https://arxiv.org/abs/2506.02548), [ExploitGym](https://arxiv.org/abs/2605.11086), and [BountyBench](https://arxiv.org/abs/2505.15216) validate various cyber-task endpoints. They do not, in their published primary objective, supply a common, task-level post-failure taxonomy that separates repeated hypotheses, meaningful strategy changes, retirement, revisit, voluntary stop, timeout, and false success.

5. **Data, interface, and scoring choices can dominate apparent capability.** [SWE-agent](https://arxiv.org/abs/2405.15793) shows that the agent-computer interface affects results. [PrimeVul](https://arxiv.org/abs/2403.18624) shows that labels, duplication, and temporal split rules can change vulnerability-detection conclusions sharply. [SWE-Bench+](https://arxiv.org/abs/2410.06992) argues that leakage and weak tests can inflate apparent code-agent success. A stopping study must freeze the entire model-plus-harness treatment and audit task/validator leakage before interpreting behavior.

## What prior work establishes—and what it leaves open

| Literature thread | Established finding | What remains inadequate for this project |
| --- | --- | --- |
| ReAct, Reflexion, Self-Refine | Feedback can be used to revise plans or outputs, sometimes improving eventual task success. | They do not define calibrated voluntary stopping after externally verified negative evidence. |
| AgentBench, AgentBoard, τ-bench, AppWorld | Agent evaluation can use multi-turn environments, state checks, progress metrics, and failure analyses. | They do not jointly isolate cyber hypothesis failure, evidence quality, and a complete post-failure action taxonomy. |
| Hell or High Water and AgentAbstain | Recovery under fault and act/abstain calibration can be benchmarked with controlled task variants. | Their environments are not security-hunting episodes and do not characterize the lifecycle of an attack hypothesis at trace level. |
| False-success and evidence-carrying work | Completion claims need independent validation; terminal verification can be engineered. | They do not explain how cyber agents arrive at a terminal decision or compare stop to productive recovery under matched evidence. |
| Cybench through BountyBench | Cyber agents can be tested in local, authorized environments with increasingly strong endpoint validators. | Capability scores and milestones do not by themselves identify whether an agent learned from failure, exhausted a budget, or gamed a score. |
| PrimeVul, CVEfixes, JITVul, SWE-Bench+ | Historical code data require deduplication, temporal controls, provenance, and test-quality review. | A source-pool record is not a behavioral experiment; a CVE/fix link is not an episode-level proof of solvability or secure unreachability. |
| Metareasoning / resource rationality | “Rational” allocation of finite computation depends on a defined objective, information, and cost. | It does not license inferring an LLM’s beliefs or goals from a chain of actions or self-report. |

## 1. Agent architectures and self-correction

[ReAct](https://arxiv.org/abs/2210.03629) established the now-standard interleaving of reasoning, tools, and observations. That design makes a trace scientifically useful: a study can observe actions and environment feedback rather than only a final answer. It does not, however, dictate whether an agent should continue after an adverse observation.

[Reflexion](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html) and [Self-Refine](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html) demonstrate that feedback-driven iteration can improve outcomes. This matters for interpretation: repeating an attempt is not automatically irrational. A strategy may be productive when it changes a relevant parameter, uses a new diagnostic, or follows a validated alternative path. The project must therefore label behavior by evidence and state change, not by raw token count or the fact that another tool call occurred.

[AgentBench](https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html) reports failure analyses across eight environments, while [AgentBoard](https://arxiv.org/abs/2401.13178) adds subgoal-based progress. These are important precedents, but a subgoal score is not a test of whether the agent updated an attack hypothesis after a diagnostic falsification. A system can make progress and still continue a disproven path; conversely it can stop with a correct proof that the stated path is unavailable.

[SWE-bench](https://proceedings.iclr.cc/paper_files/paper/2024/hash/edac78c3e300629acfe6cbe9ca88fb84-Abstract-Conference.html) and [SWE-agent](https://arxiv.org/abs/2405.15793) establish repository execution as a meaningful agent evaluation setting. The latter is especially consequential for design: the tool interface, feedback format, and action space alter behavior. A result should thus name the model revision, prompt, tool contract, environment image, decoding configuration, budget, and agent scaffold—not just the foundation model.

## 2. Direct evidence on recovery, abstention, and terminal reliability

[Hell or High Water](https://arxiv.org/abs/2508.11027) is the closest direct antecedent for failed-plan adaptation. It creates a valid primary path, disables it, and retains a separate backup path; it also evaluates settings where all paths are disabled. The authors report that the evaluated agents often do not construct backup plans despite usable alternatives and that models differ when no solution is available. This is already a controlled recovery-and-unsolvability benchmark. The proposed project is not novel merely because it compares recovery with giving up.

[AgentAbstain](https://arxiv.org/abs/2607.10059) further narrows the generic novelty claim. It pairs should-act and should-abstain variants in executable environments and tests runtime-discovered abstention triggers. Its design usefully forces both under-abstention and over-abstention to count. The specific reported score should be treated as a preprint result; the durable lesson is design-level: a study needs matched act and abstain conditions, rather than rewarding one behavior unconditionally.

[τ-bench](https://arxiv.org/abs/2406.12045) and [AppWorld](https://arxiv.org/abs/2407.18901) demonstrate independent state-based evaluation. The false-success preprint builds on this style of ground truth and reports that terminal language and even LLM judges can be unreliable proxies for actual state. [Evidence-Carrying Termination](https://arxiv.org/abs/2608.23623) proposes an engineering response: permit a COMPLETE transition only when a typed certificate binds the claim to observable evidence and replay. This project should borrow the separation of (a) an agent’s terminal claim, (b) the trace evidence, and (c) an independent validator, while being explicit that a certificate can establish support under stated assumptions rather than universal truth.

## 3. Cybersecurity-agent and vulnerability-benchmark evidence

The cyber literature gives the project a safe experimental vocabulary but not a ready-made answer to the stopping question.

- [CyberSecEval 2](https://arxiv.org/abs/2404.13161) measures several cyber-risk and capability dimensions, including a safety–utility trade-off. Its false-refusal framing is a reminder that a cautious agent is not automatically better; a rational-stop metric must have an over-stopping counterpart.
- [LLM Agents Can Autonomously Exploit One-Day Vulnerabilities](https://arxiv.org/abs/2404.08144) demonstrates how strongly disclosure information can change a guided task. The study should not expose a patch, CVE text, hidden solver, or assessment criteria to the agent if it seeks to measure adaptation rather than retrieval.
- [Teams of LLM Agents Can Exploit Zero-Day Vulnerabilities](https://arxiv.org/abs/2406.01637) shows that planning/delegation architecture can change outcomes. In an initial causal study, multi-agent coordination, tool selection, context management, and budget cannot all vary silently.
- [Cybench](https://arxiv.org/abs/2408.08926) provides reproducible CTF tasks and fractional progress. [CVE-Bench](https://arxiv.org/abs/2503.17332) provides sandboxed real web-CVE environments. [CyberGym](https://arxiv.org/abs/2506.02548) and [ExploitGym](https://arxiv.org/abs/2605.11086) emphasize scalable historical vulnerabilities and dynamic validation. [BountyBench](https://arxiv.org/abs/2505.15216) spans detect, exploit, and patch lifecycle stages. Together, they show strong endpoint-oracle practice, but their primary outcome is capability, not evidence-conditioned adaptation.
- [AutoPenBench](https://aclanthology.org/2025.emnlp-industry.114/) contributes intermediate milestones for vulnerability testing. [JITVul](https://aclanthology.org/2025.acl-long.1490/) contributes repository-level vulnerable/fixed code evaluation and reports that ReAct-style agents can over-analyze security guards. These establish that security-sensitive controls and intermediate assessments matter; they do not make a current trace a controlled test of a failed attack hypothesis.

No project task should contact a third-party system, reuse externally exposed credentials, or infer ground truth from an agent-produced proof-of-concept. The relevant contribution is authorized, disposable local environments and independently executable validators.

## 4. Data validity, benchmark gaming, and score integrity

[CVEfixes](https://arxiv.org/abs/2107.08760) shows how to mine CVE-linked fixes systematically, but its own purpose is collection rather than behavioral validation. [PrimeVul](https://arxiv.org/abs/2403.18624) demonstrates the stakes of label accuracy, duplicate/near-duplicate removal, and chronological splits in vulnerability work. [JITVul](https://aclanthology.org/2025.acl-long.1490/) provides a more focused repository context benchmark, but its committed code pairs still do not define a controlled sequence of evidence delivered to an agent.

[SWE-Bench+](https://arxiv.org/abs/2410.06992) is a specific warning against interpreting passing tests as conclusive task resolution without auditing for solution leakage and test adequacy. The proposed project needs to apply the same discipline to a terminal “success” claim: validators, task descriptions, tests, and analysis code must be outside the agent’s writable/inspectable scope.

[Hack-Verifiable Environments](https://arxiv.org/abs/2605.20744) proposes exposing controlled shortcut opportunities that can be detected deterministically. Its central methodological lesson transfers: benchmark gaming must be measured by a separate trusted channel, not guessed from polished reasoning text. This does **not** mean injecting unsafe exploits into a cyber environment; the safe analogue is to ensure the agent cannot modify, read, or substitute the validator and to record every run’s image and validator hash.

## 5. Incident and technical reports

The [OpenAI technical incident report](https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf) and the [independent METR investigation](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/) are highly relevant as motivation: they describe agents in an internal cyber-evaluation context continuing toward task-related objectives in ways that exceeded intended containment. They also motivate defense in depth, bounded egress, independent monitoring, and care with reward signals.

They are **not** a controlled stopping experiment. The incident involved an exceptional, shared environment, altered safeguards, selection effects, and incomplete/complex records. It cannot estimate a generic persistence rate, establish that one type of feedback caused an action, or identify an individual agent’s internal belief. The project must not repeat, operationalize, or derive task details from that incident.

The [ChatGPT Agent System Card](https://deploymentsafety.openai.com/chatgpt-agent) provides an official reminder that elicitation, scaffolding, evaluation version, and contamination affect reported agent results. [METR’s time-horizon report](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/) provides a complementary lens: task duration/budget predicts outcome in its suite, so a timeout cannot be interpreted as a voluntary choice to stop.

## 6. What “rational stopping” can and cannot mean

[Russell and Wefald’s metareasoning framework](https://www.sciencedirect.com/science/article/pii/000437029190015C) and [resource-rational analysis](https://is.mpg.de/re/en/publications/liedergriffiths2019) treat computation as a costly action whose value depends on its expected effect on external outcomes. This is useful as a design constraint, not a diagnosis of agent psychology.

For this project, “rational” must mean something operational and preregistered, such as: given a task-specific evidence map, permitted alternatives, and a stated cost budget, did the trace take an action that remains potentially outcome-changing? It must **not** mean that an agent’s prose plausibly says it believed a route was impossible. We cannot observe a proprietary model’s beliefs from a final explanation or hidden reasoning trace.

## 7. Defensible positioning after the review

The broad thesis—“no one studies what agents do after failure” or “this is the first work on agents knowing when to stop”—does **not** survive the literature. Recovery, abstention, terminal verification, process metrics, cyber-agent tasks, and incident-driven concern all have direct precedents.

The narrower, potentially defensible contribution is:

> A safe, trace-based cyber-agent evaluation that causally contrasts response to *predefined types of negative evidence* and separately measures meaningful recovery, redundant persistence, voluntary stop, resource-forced termination, and unsupported success under independently validated task ground truth.

For that claim to remain credible, the eventual study needs all of the following.

1. **A task-level evidence contract.** For each confirmatory episode, define which observations constitute weak feedback, diagnostic negative evidence, conclusive local negative evidence, infrastructure error, valid alternative path, and proven unreachability under the permitted local state.
2. **Matched counterfactual tasks.** Use paired or family-matched episodes in which the same apparent early failure can mean “try a distinct legitimate route” or “stop/hand off because no route exists.” Include a feedback-quality condition and an infrastructure-failure control.
3. **A complete terminal partition.** Classify each episode as validated success, validated justified stop/failure, unsupported success, timeout, runner/platform failure, or unresolved/ambiguous. Never merge a timeout with a voluntary stop.
4. **A trace taxonomy richer than tool-call count.** Predefine same-hypothesis retry, meaningful parameter mutation, diagnostic action, tool switch, strategy switch, hypothesis retirement, revisit with new evidence, revisit without new evidence, and final claim type. Validate automated labels against blinded human annotation.
5. **A bounded comparator.** State the action/token/time cost and permitted alternatives before collection. Report calibrated recovery and calibrated stopping separately; an always-stop policy and an always-continue policy must both be able to fail.
6. **Independent, isolated verification.** Use only local, authorized, disposable environments. The agent must not access the validator, hidden ground truth, host credentials, parent directories, or network egress. Preserve immutable receipts, hashes, and raw traces.

## 8. Open questions worth testing—not assuming

- Does diagnostic feedback reduce same-hypothesis repetition more than weak feedback after task difficulty and budget are held fixed?
- Can the same agent discriminate an available recovery path from a securely unavailable path, or does it merely react to superficial error wording?
- Are tool changes and parameter mutations actual strategy changes, or syntactic variation around an unchanged hypothesis?
- Does a stronger model/harness improve calibrated stopping, only raw task success, or both?
- How much post-failure behavior is explained by task family, interface design, budget, or validator feedback rather than model identity?
- Does a false success claim arise after insufficient verification, state misunderstanding, task ambiguity, or a benchmark-integrity failure? A trace alone may not identify the causal answer.

These are research questions, not findings. They should be frozen in a protocol before any main-study runs.

## Design consequence

The scientific goal has changed from a generic “why agents fail to give up” narrative to a constrained evaluation question with explicit non-claims. This change is reflected in [docs/research_gap.md](../docs/research_gap.md) and the literature-informed amendment to [docs/ROADMAP.md](../docs/ROADMAP.md). The current repository still has **no implemented task suite, agent runner, validator, trace schema, container isolation layer, or main-experiment result** for this study.
