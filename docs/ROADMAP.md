# Roadmap: From Audit to a Defensible *When to Stop* Paper

**Project:** *When to Stop: How AI Agents Adapt After Failed Attacks and Why They Fail to Give Up*  
**Starting point:** audit completed on 2026-09-28; the current checkout is an AVB-Bench package with reusable methodology, a local stopping-study engineering fixture, and no provider-backed stopping-behavior experiment.  
**Status rule:** nothing below authorizes a main experiment by itself. A phase begins only after its gate is met and its safety/research decisions are recorded.

## Guiding principle

The paper should not ask merely whether an agent succeeds. It should measure what the agent does after evidence contradicts a plausible attack hypothesis, and distinguish adaptive exploration from redundant persistence, budget-driven termination, and unsupported success claims.

The minimum defensible contribution is a controlled, safe, trace-based measurement of post-failure adaptation for a declared agent configuration. It is not a claim about all AI agents, all cyber operations, or an agent's unobservable internal beliefs.

## Literature-informed design amendment — 2026-09-28

**Status:** literature review completed; main experiment remains **NOT STARTED**. See [the evidence matrix](../literature/literature_matrix.csv), [review](../literature/literature_review.md), and [research-gap assessment](research_gap.md).

The review changes the project positioning and protocol requirements:

- Do **not** claim firstness for stopping, abstention, recovery, trajectory evaluation, false-success detection, or realistic cyber-agent evaluation. [Hell or High Water](https://arxiv.org/abs/2508.11027) and [AgentAbstain](https://arxiv.org/abs/2607.10059) are direct recovery/abstention precedents; [AgentBoard](https://arxiv.org/abs/2401.13178) is a process-metric precedent.
- The primary estimand must be a **calibrated contrast**, not raw persistence: response after predefined negative evidence in a recoverable episode versus a securely unavailable episode. An always-stop and an always-continue policy must both be able to fail.
- Treat feedback meaning as an experimental factor. At minimum distinguish diagnostic negative evidence, weak/non-diagnostic feedback, and infrastructure failure. Do not attribute a reaction to “failure” if the agent only saw a transport or tool fault.
- Record a task-level hypothesis/evidence contract before collection: permitted alternatives, known path status, what counts as a relevant parameter mutation, and the proof or independent justification for secure unreachability.
- A terminal message is never ground truth. Use an independent deterministic validator and retain a distinct `unsupported_success` state, following the design concern raised by [false-success](https://arxiv.org/abs/2606.09863) and [evidence-carrying termination](https://arxiv.org/abs/2608.23623) work.
- Treat model, prompt, tool interface, scaffold, permissions, budget, evaluator, and environment image as a single versioned treatment. [SWE-agent](https://arxiv.org/abs/2405.15793) and benchmark-validity work show that these choices can change outcomes.
- Restrict tasks to local, authorized, disposable environments. Incident reports are motivation for containment and independent validation only; they are not a task source or causal dataset.

**Protocol consequence:** The final paper’s credible contribution is a cyber-specific, evidence-conditioned behavioral measurement layer over validated local tasks—not a generic claim that agents “do not know when to stop.”

## Phase 0 — Preserve and reconcile the starting state

**Status:** Partially complete: this audit documents the present checkout. Recovery work is **NOT STARTED**.

**Deliverables**

- immutable snapshot of this research package;
- recovered AVB artifact (if available) with exact Git revision, manifest hashes, raw traces, results, and licenses;
- a source-of-truth map identifying which manuscript/protocol/result ledger is authoritative;
- reconciliation note for the documented 15-run exploratory state versus the documented 144-run state;
- project Git repository, release tag, and ignore policy that preserve raw data separately from derived/public data.

**Gate to Phase 1**

- Every inherited AVB number is either reproducible from a retained artifact or labelled historical/unverified.
- The new study's files are clearly separated from legacy AVB materials.

## Phase 1 — Define the scientific object

**Status:** A formal [preregistration draft](preregistration.md) now exists. The task manifest, coding calibration, power simulation, configuration freeze, and all main-experiment work remain **NOT STARTED**.

**Goal**

Turn the intuitive phrase "fails to give up" into observable, falsifiable constructs.

**Deliverables**

- final research question and scope statement;
- preregistered definitions of attempt, attack hypothesis, observation, negative evidence, conclusive negative evidence, parameter mutation, tool switch, strategy switch, hypothesis abandonment, revisit, agent stop, system timeout, infrastructure failure, and false success;
- a causal/measurement diagram showing task state, feedback quality, agent configuration, actions, validator state, budget, and final outcome;
- primary and secondary hypotheses, including null/alternative interpretations;
- explicit non-claims: no inference about internal belief from prose alone, no universal agent claim from one configuration, and no live-target generalization.

**Critical design decision**

Define whether the core estimand is:

1. behavior after *conclusive local negative evidence*;
2. discrimination between solvable and securely unsolvable tasks;
3. adaptation under controlled feedback quality; or
4. a combination with one predeclared primary endpoint.

Do not optimize the task suite until this choice is frozen.

**Gate to Phase 2**

- At least two independent reviewers can label a small set of scripted example traces using the definitions with acceptable agreement.
- The primary endpoint does not count a timeout as voluntary stopping.

## Phase 2 — Design a safe, validated task suite

**Status:** A nine-task local finite-state pilot architecture now exists under benchmark/. Its static quality validation passes. A scripted in-memory adapter/sandbox/verifier/logger smoke fixture now exercises one path, but it is not an AI agent, a runtime-isolation result, or a scientific pilot. Independent task review, an approved runtime, provider-backed agent integration, and all main-experiment collection remain **NOT STARTED**.

**Goal**

Create local authorized episodes in which success, failure, and the evidentiary meaning of feedback are objectively testable.

**Task strata**

| Stratum | Purpose | Confirmatory use |
| --- | --- | --- |
| Solvable recovery | The first plausible hypothesis fails, but an alternative valid path remains. | Tests strategy revision rather than mere stopping. |
| Securely unsolvable | The stated goal is blocked under the permitted local state, with an independently checked reason. | Tests recognition of futility and calibrated stopping. |
| Multi-path | Several plausible hypotheses exist; some fail and one may succeed. | Separates productive exploration from repetition. |
| Feedback-quality matched pair | Same underlying task family with diagnostic versus weak feedback. | Tests whether behavior responds to evidence quality. |
| Infrastructure control | Controlled tool/transport failure without task-level security information. | Prevents platform errors from being interpreted as reasoning failures. |

**Deliverables**

- a versioned task manifest and opaque IDs;
- task-specific deterministic success validators;
- reference solutions or proofs of unreachability under stated constraints;
- a negative-evidence map and allowed alternative paths for every confirmatory task;
- independent ground-truth, purity, leakage, and safety review;
- task-family balance plan and clustering map;
- an explicit exclusion register for ambiguous or unsafe cases.

**Safety boundary**

Use only self-contained local environments and authorized source. No probing, credential use, production access, or third-party target is part of this project.

**Gate to Phase 3**

- All confirmatory tasks have deterministic validators and two-reviewer ground truth.
- The task suite includes both success-possible and secure-stop cases; it does not equate all failures with unsolvability.
- Safety review approves the task images and data policy.

## Phase 3 — Build the experiment harness and trace contract

**Status:** Partially implemented, but **NOT ELIGIBLE FOR PROVIDER-BACKED OR
CONTAINERIZED EPISODES**. The repository now contains a fail-closed Docker policy,
pre-start effective-configuration inspection, cleanup receipt, and a nine-part safety
test harness under `sandbox/`; see `docs/safety.md`. It also contains a provider-neutral
adapter interface, evaluator-owned public-task projection, append-only JSONL logger,
immutable manifest/receipt format, independent verifier wiring, and one deterministic
in-memory scripted smoke fixture. There is still no approved immutable image, passing
runtime safety suite, provider-backed agent adapter, runtime-hidden validator deployment
for a container, frozen provider configuration, or main-study trace store. No
containerized agent or main-experiment episode has been launched.

**Preflight update — 2026-09-29:** the requested controlled-pilot gate was exercised
without launching an agent. All nine declarative task/verifier contracts and the
scripted log/receipt fixture pass, but the runtime safety suite correctly fails closed
because no reviewed immutable image exists; Git provenance is also unavailable. The
pilot is blocked. See [pilot report](pilot_report.md).

**Goal**

Make each episode reproducible and make the central behavior observable without exposing labels to the agent.

**Deliverables**

- pinned container/VM image and dependency lockfiles;
- per-episode isolated runtime with default-deny egress, no host secrets, no parent-directory access, resource limits, and disposable storage;
- frozen agent-configuration manifest: model revision, provider/CLI, prompts, tools, permissions, decoding settings where available, budget, image digest, and randomization seed;
- append-only trace event schema with action ID, time, tool/command, redacted input, observation, exit status, validator feedback pointer, explicit stop rationale, and final claim;
- separate hidden validator channel that records truth without leaking it into the workspace;
- resumable job runner that preserves partial traces, classifies transport/platform failures, and never overwrites a previous episode;
- scripted fixture traces and end-to-end replay tests.

**Acceptance tests**

- a deliberately repeated command is distinguishable from a parameter change;
- an agent finalization is distinguishable from timeout and runner crash;
- a false final-success claim is rejected by the validator;
- the agent cannot read ground-truth, validator, host, or parent-directory files;
- replaying a fixture produces the same derived labels and checksums.

**Gate to Phase 4**

- Threat model and isolation tests pass.
- Trace completeness, redaction, and validator separation are independently reviewed.
- No scored agent outcomes have yet been used to alter the confirmatory protocol.

## Phase 4 — Instrumentation pilot, not a main experiment

**Status:** **NOT STARTED.**

**Goal**

Validate the measurement system with a small, explicitly non-confirmatory pilot.

**Deliverables**

- pilot run log with all transport failures retained;
- audit of trace loss, validator leakage, sandbox escape attempts, and task flakiness;
- blinded annotation pilot and inter-rater agreement report;
- task calibration report: observed runtime/resource distribution, feedback clarity, ambiguity, and validator stability;
- revised codebook and harness only for documented measurement defects, not to optimize performance.

**Decision rules**

- Remove or demote ambiguous tasks before the main study.
- Fix logging/validator/isolation defects before collecting confirmatory data.
- Record all changes as protocol version changes; do not merge pilot and main outcomes.

**Gate to Phase 5**

- The event taxonomy is usable and reliable.
- Every retained task remains safe, stable, and classifiable.
- The budget is sufficient to observe deliberate stops in principle, not just forced timeouts.

## Phase 5 — Freeze preregistration and analysis plan

**Status:** **NOT STARTED.**

**Goal**

Prevent adaptive redefinition of persistence after outcomes are visible.

**Deliverables**

- frozen task list, image digests, task hashes, labels, exclusions, and randomization schedule;
- frozen agent configuration(s), prompts, tools, time/token/action budgets, and collection window;
- primary endpoint and decision rule; secondary endpoints and exploratory labels;
- sample-size/power or simulation rationale at the task-episode level;
- plan for hierarchical/cluster-aware uncertainty, paired contrasts, missing data, and multiple comparisons;
- blinded adjudication protocol, coder-training material, disagreement process, and codebook version;
- safety and data-governance sign-off.

**Recommended endpoints**

Report separate quantities rather than a single composite score:

- explicit agent-stop rate before resource exhaustion;
- time/actions after conclusive negative evidence;
- same-hypothesis retry rate versus meaningful adaptation rate;
- hypothesis-retirement latency;
- successful recovery after an initially failed path;
- revisit rate with and without new evidence;
- valid success, valid failure, unsupported success, timeout, and infrastructure-failure rates;
- ability to differentiate solvable from securely unsolvable tasks.

**Gate to Phase 6**

- A dated protocol freeze exists.
- Pilot data are locked out of confirmatory analysis.
- Any agent/tool/provider change is defined as a new configuration, not a silent continuation.

## Phase 6 — Main data collection

**Status:** **NOT STARTED.**

**Goal**

Collect complete episodes under the frozen protocol.

**Procedure**

1. Verify task/image/configuration hashes before each batch.
2. Randomize and counterbalance task order and feedback condition as preregistered.
3. Run isolated episodes without advisory, hidden validator, or cross-task leakage.
4. Preserve raw traces, final outputs, environment receipts, usage/budget records, and all failed transport attempts.
5. Resume only from recorded checkpoints; never silently rerun or overwrite an episode.
6. Monitor safety/infrastructure health without viewing protected ground-truth labels or altering task content.

**Gate to Phase 7**

- Collection completeness and exclusions are frozen.
- Raw trace hashes, configuration manifests, and task-version mapping are complete.
- No unplanned tuning was performed; any deviation is documented and stratified.

## Phase 7 — Verification and blinded adjudication

**Status:** **NOT STARTED.**

**Goal**

Turn traces into defensible behavioral labels without letting expected task status bias review.

**Deliverables**

- deterministic validator outcomes for every final claim;
- blinded coder labels for evidence type, hypothesis change, strategy change, revisit, stop rationale, and ambiguity;
- inter-rater agreement and adjudication log retaining original disagreements;
- final episode classification: valid success, valid failure/stop, unsupported success, unresolved, timeout, or infrastructure failure;
- audit of label leakage and exclusion decisions.

**Gate to Phase 8**

- Labels are complete or missingness is explicitly classified.
- All confirmatory analyses use the frozen codebook and denominator rules.

## Phase 8 — Statistical analysis and robustness checks

**Status:** **NOT STARTED.**

**Primary analysis principles**

- Treat task episode as the main unit; actions are nested observations, not independent samples.
- Cluster uncertainty by task, task family, seed, and agent configuration as appropriate.
- Separate voluntary stop, timeout, and runner failure.
- Separate successful recovery, futile persistence, and unsupported final success.
- Present counts/denominators, uncertainty intervals, and trace examples that are safe to release.
- Use paired tests only for genuinely paired, predeclared endpoints; use hierarchical or count/time models only when the data support them.

**Robustness work**

- sensitivity to the definition of conclusive negative evidence;
- sensitivity to task difficulty, feedback verbosity, and budget;
- leave-one-task-family-out checks;
- model/CLI/prompt revision as separate configurations, never pooled by default;
- analysis of censored traces and missing events;
- negative-control/infrastructure-control outcomes;
- optional replication on a second frozen agent configuration only after the first result is stable.

**Gate to Phase 9**

- Confirmatory and exploratory results are visibly separated.
- Alternative explanations have been tested or recorded as unresolved.
- No claim depends on unverified internal reasoning or live-target behavior.

## Phase 9 — Paper, artifact, and responsible release

**Status:** **NOT STARTED.**

**Paper structure**

1. Motivation: outcome-only cyber-agent evaluations miss the behavior after failure.
2. Precise problem definition and non-claims.
3. Safe task design, failure-feedback contract, and isolation architecture.
4. Trace instrumentation, verifier, and blinded annotation protocol.
5. Experimental design and statistical plan.
6. Results: stop/timeout/adaptation/false-success outcomes with denominators and uncertainty.
7. Mechanistic interpretation bounded by observable evidence.
8. Threats to validity, safety, reproducibility, and generalization limits.
9. Release and ethics statement.

**Artifact package**

- source release tag and dependency lockfiles;
- safe task manifests, image digests, validators, and sandbox policy;
- redacted raw/derived traces with schema and checksums;
- annotation codebook and agreement data;
- analysis scripts that regenerate every figure/table from raw released data;
- exclusion, safety, provenance, and license ledgers;
- an executable `reproduce` path that works from a clean environment.

**Publication gate**

- The exact studied configuration is named.
- The paper never calls timeout rational stopping or calls a model narrative its internal belief.
- The task suite, results, and release artifacts are independently reproducible.
- Any unsafe or nonredistributable material is omitted with a documented reason.

## Immediate priority order

1. Preserve/recover the missing AVB artifact and establish Git provenance.
2. Decide whether *When to Stop* is a separate repository or a versioned subproject.
3. Freeze the operational definitions and causal diagram.
4. Design task strata and safety/validator requirements.
5. Build only the trace/validator/isolation pilot after those decisions are approved.
6. Do not collect main-study agent outcomes until Phases 1–5 have passed their gates.

No main experiment has been started by this roadmap.
