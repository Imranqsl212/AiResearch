# Research gap: *When to Stop*

**Project:** *When to Stop: How AI Agents Adapt After Failed Attacks and Why They Fail to Give Up*  
**Assessment date:** 2026-09-28  
**Decision status:** design only; no main experiment has started.

## Short answer

The generic claim that agents are evaluated only by goal completion, or that no one studies recovery, abstention, terminal reliability, or post-failure behavior, is not defensible. Recent work already measures each of those constructs in at least one setting.

A narrower empirical gap may survive:

> In safe, local cybersecurity episodes, existing work does not yet provide a common, preregistered, trace-level measurement that contrasts **diagnostic negative evidence**, **recoverable failure**, **securely unavailable goals**, and **infrastructure failure**, while separately validating recovery, voluntary stopping, timeout, and unsupported success.

This is a claim about an evaluation design, not an assertion that no prior work has observed related behavior.

## Evidence map

| Existing work measures X | Existing work observes Y | It does not adequately measure Z for this project | Proposed Z |
| --- | --- | --- | --- |
| [ReAct](https://arxiv.org/abs/2210.03629), [Reflexion](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html), and [Self-Refine](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html) measure performance after feedback/reflection. | Iteration and feedback can improve eventual outcomes. | Whether a particular externally observed failure should trigger retry, a meaningful alternative, stop, or handoff in a cyber episode. | Label the post-evidence action sequence and evaluate recovery/stop calibration separately. |
| [AgentBench](https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html) and [AgentBoard](https://arxiv.org/abs/2401.13178) measure failure categories and intermediate progress. | Final success hides process differences. | A task-specific map from negative evidence to attack-hypothesis retirement, revisit, and strategy switch. | An evidence-and-hypothesis trace codebook, independently annotated and validator-linked. |
| [Hell or High Water](https://arxiv.org/abs/2508.11027) measures backup planning after controlled external failures and includes no-solution conditions. | Agents can struggle to use alternatives and can exhaust budgets when no solution is available. | Cybersecurity-specific reasoning with equivalent early signals whose correct response is recovery in one case and stop in another; fine-grained repeated-hypothesis measurement. | Matched local cyber-task families with a specified alternative-path/unreachability contract. |
| [AgentAbstain](https://arxiv.org/abs/2607.10059) measures paired should-act/should-abstain behavior. | Tool-use abstention is distinct from raw task competence, and both under- and over-abstention matter. | The lifecycle after an agent has already investigated a plausible security hypothesis and accumulated different kinds of evidence. | Paired/calibrated recovery-versus-stop decisions after defined runtime evidence. |
| [τ-bench](https://arxiv.org/abs/2406.12045), [AppWorld](https://arxiv.org/abs/2407.18901), [false-success analysis](https://arxiv.org/abs/2606.09863), and [Evidence-Carrying Termination](https://arxiv.org/abs/2608.23623) measure state validity or terminal evidence. | A confident completion message can conflict with independently checked state; terminal verification can be engineered. | Cyber-agent false success together with the preceding evidence/strategy process and a separate stop state. | Independent validator receipts plus a terminal partition: valid success, justified stop/failure, unsupported success, timeout, platform failure, unresolved. |
| [Cybench](https://arxiv.org/abs/2408.08926), [AutoPenBench](https://aclanthology.org/2025.emnlp-industry.114/), [CVE-Bench](https://arxiv.org/abs/2503.17332), [CyberGym](https://arxiv.org/abs/2506.02548), [ExploitGym](https://arxiv.org/abs/2605.11086), and [BountyBench](https://arxiv.org/abs/2505.15216) measure cyber task capability. | Cyber agents can be assessed in local/reproducible environments, and intermediate milestones or dynamically validated endpoints are possible. | A shared post-failure behavior taxonomy and causal contrast of feedback meaning across safe cyber cases. | An explicitly bounded cyber-agent behavioral benchmark, not a live attack evaluation. |
| [PrimeVul](https://arxiv.org/abs/2403.18624), [CVEfixes](https://arxiv.org/abs/2107.08760), [JITVul](https://aclanthology.org/2025.acl-long.1490/), and [SWE-Bench+](https://arxiv.org/abs/2410.06992) measure data validity, repository context, and benchmark leakage. | Labels, duplicates, temporal leakage, and weak tests can substantially alter apparent performance. | Episode-level proof that a task is genuinely recoverable or securely unavailable under the stated agent permissions. | Per-task ground-truth/evidence manifests, provenance hashes, leakage review, and task-family clustering. |
| [Russell and Wefald](https://www.sciencedirect.com/science/article/pii/000437029190015C) and [Lieder and Griffiths](https://is.mpg.de/re/en/publications/liedergriffiths2019) formalize computation under resource limits. | A rational choice depends on objective, information, and computational cost. | An observable, preregistered cost-aware comparator suitable for proprietary tool agents. | Define bounded “potentially outcome-changing action” rules and costs; do not infer internal belief or universal rationality. |

## What the study may claim

If the protocol satisfies the conditions below, the paper may claim:

> For the named agent configurations and local task distribution, the study estimates how behavior after predefined evidence differs between recoverable, securely unavailable, weak-feedback, and infrastructure-control episodes.

It may report calibrated recovery, calibrated stopping, repeated-hypothesis behavior, timeout, and unsupported-success rates with uncertainty. It may compare these outcomes across preregistered conditions.

It must not claim:

- that it is the first study of agent stopping, abstention, recovery, false success, or trajectory evaluation;
- that a timeout is an agent’s chosen stop;
- that an explanation or chain-of-thought reveals a model’s true belief, intention, or goal;
- that an observation in a local sandbox generalizes to all models, all cyber operations, or live targets;
- that continuing after failure is intrinsically irrational without a predeclared objective, action cost, evidence contract, and available alternatives.

## Alternative explanations that threaten novelty

### Objection 1 — The core phenomenon is already measured by recovery and abstention benchmarks

[Hell or High Water](https://arxiv.org/abs/2508.11027) deliberately causes a path to fail while preserving a backup and also examines no-solution cases. [AgentAbstain](https://arxiv.org/abs/2607.10059) supplies matched act/abstain tasks, including runtime-discovered triggers. If the project merely asks “do agents keep trying after a tool fails?” or “do they know when to stop?”, then it duplicates these works.

**Assessment:** this objection defeats a generic novelty claim. The gap survives only if the project measures a cyber-task-specific evidence/hypothesis lifecycle, with explicit distinctions unavailable from the broader recovery/abstention outcomes.

### Objection 2 — Progress and trajectory analyses already go beyond endpoint scores

[AgentBoard](https://arxiv.org/abs/2401.13178) uses progress rate; [AgentBench](https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html) analyzes failure reasons; [AutoPenBench](https://aclanthology.org/2025.emnlp-industry.114/) exposes cyber-task milestones; [BountyBench](https://arxiv.org/abs/2505.15216) separates detect, exploit, and patch. A paper framed as “we inspect trajectories instead of final success” would therefore be unoriginal.

**Assessment:** this objection defeats a process-metric novelty claim. The gap survives only if the proposed taxonomy is tied to independently defined *negative evidence* and to a hypothesis/strategy state transition—not merely additional milestones or generic progress.

### Objection 3 — False success and evidence-backed termination already address unsafe completion

The [false-success study](https://arxiv.org/abs/2606.09863) directly compares completion claims with ground truth, and [Evidence-Carrying Termination](https://arxiv.org/abs/2608.23623) tests a completion gate. A contribution framed only as “agents may claim success without proof” would be late.

**Assessment:** this objection defeats false success as a standalone novelty claim. The gap survives only if false success is one preregistered terminal outcome linked to an evidence trajectory, not the sole contribution.

### Objection 4 — Cyber benchmarks already have isolation, realistic tasks, and oracles

[CVE-Bench](https://arxiv.org/abs/2503.17332), [CyberGym](https://arxiv.org/abs/2506.02548), and [ExploitGym](https://arxiv.org/abs/2605.11086) already show local cyber environments and dynamic validation. Recreating a generic CVE-exploitation benchmark would add little and could introduce unnecessary dual-use risk.

**Assessment:** this objection defeats “first realistic cyber benchmark.” The gap survives only as a behavioral measurement layer with safe task construction, explicit unreachability proofs, and no external target interaction.

### Objection 5 — The incident reports have already shown dangerous persistence

The official [OpenAI report](https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf) and [METR investigation](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/) make persistence, reward hacking, and insufficient containment empirically salient. One might argue that the project only repackages a well-known incident.

**Assessment:** the reports are compelling motivation, but they are incident-specific, observational, and heavily confounded. They do not substitute for a controlled, reproducible, safe study. The gap survives as a *measurement* gap, not a claim that persistence has never been observed.

### Objection 6 — “Rational stopping” is already a mature theoretical problem

Metareasoning and resource-rationality formalize the allocation of limited computation. If the project presents a new theory of rational stopping without a new formal contribution, it is unlikely to be novel.

**Assessment:** this objection defeats a broad theoretical novelty claim. The gap survives only as an empirical operationalization: test whether observable agent behavior accords with a declared, bounded comparator under controlled evidence, without claiming access to beliefs.

## Verdict: does the gap survive?

**Yes, conditionally and narrowly.** It survives as a missing synthesis and evaluation design at the intersection of:

1. **safe local cyber tasks;**
2. **paired recoverable versus securely unavailable states;**
3. **evidence-quality manipulation rather than only task difficulty;**
4. **trace-level labels for repetition, mutation, tool/strategy change, retirement, revisit, and final claim;**
5. **independent state/validator receipts;** and
6. **separate calibrated recovery, calibrated stopping, timeout, and false-success estimands.**

The gap does **not** survive as a claim of firstness for stopping, abstention, recovery, trajectory analysis, false-success detection, or realistic cyber-agent evaluation.

## Revised research questions

The main study should choose one preregistered primary question rather than treating all as equivalent.

1. **Primary candidate:** After an independently defined conclusive local negative-evidence event, do named cyber-agent configurations change to a potentially outcome-changing strategy at different rates in recoverable versus securely unavailable episodes?
2. **Calibration candidate:** Can the same configuration distinguish a valid recovery path from an unavailable path without becoming an always-stop or always-continue policy?
3. **Feedback candidate:** Does diagnostic feedback, compared with weak but non-deceptive feedback, change same-hypothesis repetition, hypothesis-retirement latency, and valid recovery when task family and budget are held fixed?
4. **Reliability candidate:** How often does a terminal success claim lack independent validator support, and how is that rate related to the prior evidence trajectory?

## Design gates implied by the gap

Before any main experiment, the project must:

- freeze a task manifest with permitted tools, alternatives, deterministic success validators, and proof/argument of secure unreachability for stop cases;
- ensure agents cannot inspect or change the validator, hidden ground truth, image build, host, parent directories, or network; 
- record whether termination was agent-initiated, budget-forced, runner-caused, or unresolved;
- prespecify the action and hypothesis codebook, annotation agreement threshold, missing-data policy, and task-family clustering;
- define a paired-calibration primary endpoint and report over-stopping as well as futile persistence;
- treat model revision plus scaffold/tool interface as one configuration; and
- keep the pilot separate from all confirmatory runs.

The complete source-by-source evidence is in [literature/literature_matrix.csv](../literature/literature_matrix.csv). The associated design changes are appended to [ROADMAP.md](ROADMAP.md).
