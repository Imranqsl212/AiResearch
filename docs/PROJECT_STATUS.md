# Project Status Audit

> **Later infrastructure note (2026-09-29):** This audit preserves its original
> evidence snapshot. Git baseline `33b3d7acfc7cea0b83f96bae9f2f26d0127152da`
> now exists and the old AVB materials were moved to a recoverable Trash archive.
> A digest-pinned image *candidate* was built, but its preapproval safety check
> failed; it is not approved. See [current readiness](EXPERIMENT_READINESS.md).

> **Post-audit implementation update — 2026-09-29:** The original audit snapshot below
> predates the local stopping-study pilot and execution plumbing. The checkout now
> contains a nine-task declarative benchmark, task/trajectory schemas, an evaluator-owned
> local validator/oracle, a provider-neutral adapter interface, an append-only observable
> trajectory logger, versioned manifests/receipts, and a deterministic in-memory scripted
> smoke fixture. It still contains no provider-backed agent result, approved task image,
> passing container safety gate, or main experiment. See docs/benchmark_design.md,
> docs/logging.md, docs/reproducibility.md, and docs/preregistration.md.

**Audit date:** 2026-09-28  
**Requested project:** *When to Stop: How AI Agents Adapt After Failed Attacks and Why They Fail to Give Up.*  
**Audit scope:** the current checkout at `/Users/imranmzakirov/Desktop/research`. This is a read-only audit of existing material plus the creation of this status record and `docs/ROADMAP.md`. No main experiment, agent run, repository clone, build of untrusted code, or external attack was started.

## Executive Summary

The current checkout is an AVB-Bench research package, not yet a completed implementation of the requested *When to Stop* study. Its existing scientific focus is whether a frozen AI security-agent configuration can distinguish deliberately vulnerable repositories from matched secure controls. It contains manuscripts, figures, templates, a submission scaffold, a small AVB-Bench v2 **metadata-only** discovery pipeline, a nine-task local stopping-study fixture, a provider-neutral observable execution interface, and an unapproved fail-closed Docker sandbox policy. It still does **not** contain a provider-backed agent adapter, approved task image, hidden runtime oracle deployment for a container, collected model traces, results ledger, Docker Compose deployment, dependency lockfile, or Git history that its older documentation references.

The most useful reusable ideas are the existing insistence on controlled negative examples, explicit claim boundaries, outcome adjudication, configuration freezing, clustered analysis, and local-only safety principles. Those are a strong starting point for a stopping-behavior study, but they do not measure adaptation after failure. No current evidence supports a claim about whether agents rationally stop, repeat, mutate strategy, learn from negative evidence, or falsely declare success.

There is also an evidence-state conflict that must be resolved before the prior AVB results are reused: `README.md` and `QUICK_READ.md` describe a 15-run exploratory partial batch, whereas `full_paper_draft.md`, `journal_submission.md`, and `submission/main.tex` describe a completed 144-run batch. The raw artifact and raw traces needed to reconcile those claims are absent from this checkout. Both statements are therefore treated here as **documented but not locally verifiable**.

A separate read-only deep security review was started during this audit and deliberately left **PENDING** at the user's request. Its absence from this document is not a clean security result.

## Repository State

### Verified in this checkout

| Area | Observed state |
| --- | --- |
| Workspace size | About 15 MB, 104 files, and 19 directories at audit time. |
| Version control | **NOT IMPLEMENTED in this checkout.** `git rev-parse` reports that this directory is not a Git repository; no local Git history or immutable revision can be audited. |
| Research focus represented in files | AVB-Bench / AI vulnerability discovery and secure-control discrimination, not stopping behavior. A text search found no existing formulation of the requested *When to Stop* study. |
| Manuscript assets | Markdown manuscripts, a LaTeX submission scaffold, PDFs/DOCX/PPTX, figures, poster assets, and manuscript-generation scripts are present. |
| v2 data-model layer | `schemas/candidate.schema.json`, source registry/configuration, taxonomy, and small Python modules for metadata discovery and processing are present. |
| Tests | Six Python unit tests for selected v2 helper behavior are present and passed during this audit. |
| Local contract check | `reproduce.sh` passed; it validates JSON/configuration only and explicitly does not call APIs, clone repositories, build, or execute target code. |
| Submission checks | `make -C submission validate` passed its static anonymity/section/citation/figure checks. It did not rebuild the paper. |
| Containers | Docker and Docker Compose binaries exist on the host. A restricted image template, immutable-image allow-list, runner, and safety harness now exist under `sandbox/`; the allow-list is empty and no runtime isolation test has passed. Docker Compose and a runnable approved task image remain **NOT IMPLEMENTED**. |

### Absent from this checkout

The following components are referenced by older documents as part of `../AI-BugBounty-Blindness-Benchmark/`, but that sibling artifact is not present and cannot be verified here:

- AVB-Bench generated repositories and their manifests;
- hidden behavioral oracles and their source code;
- `agents/codex_agent.py`, prompts, schema, and agent configuration records;
- `evaluation/` code, raw JSONL event logs, adjudication ledgers, and generated results;
- `results/summary*.json`, purity-audit files, and cluster-statistics artifacts;
- the claimed complete Docker/reproducibility package and approved task image;
- protocol subdocuments referenced under `protocol/`;
- the benchmark Git commit/hash and raw history needed to verify the reported runs.

The absence is an observation about this checkout, not evidence that those files never existed elsewhere.

## Existing Infrastructure

### Verified and reusable

1. **Research documentation and claim discipline.** The existing protocol distinguishes targets from controls, notes that repeated runs are not independent cases, calls for blinded adjudication, and warns against universal claims from one agent configuration. `docs/CLAIMS.md` and `docs/FINAL_RESEARCH_AUDIT.md` are particularly conservative.
2. **AVB-Bench v2 candidate contract.** The candidate schema is versioned (`2.0`) and includes repository, vulnerability, pair, validation, provenance, hard-negative, deduplication, and split fields.
3. **Metadata-first pipeline skeleton.** `pipeline/` contains normalizers for saved NVD/CVE, GHSA, OSV, and SWE-style exports; a GitHub metadata-search client; filtering, signal mining, candidate construction, patch-diff summary, exact-key deduplication, triage, and deterministic split helpers.
4. **Safe default behavior.** The normalizer path and `reproduce.sh` are metadata-only. The GitHub module describes itself as GET-only and does not clone repositories. The patch helper uses argument-vector `git diff`, not `shell=True`.
5. **Research-operation templates.** CSV templates exist for run logging, real-world cases, human sessions, public-case evidence, and personal report review. These are empty templates rather than collected study data.
6. **Presentation and writing toolchain.** Static submission validation succeeds locally. Existing scripts generate manuscript, figure, poster, and presentation artifacts, although their dependencies are not declared by the project.

### Documented but not verified here

Older AVB material describes a matched-pair benchmark, a Codex runner, hidden oracles, a 144-run collection, control-purity review, and cluster-aware statistics. The documents show thoughtful design intent, but none of the executable artifact, inputs, output traces, or provenance records are available in this checkout for independent verification.

## Existing Research

### What the existing project studies

The available documents frame AVB-Bench around a narrower question: whether an AI security agent can find vulnerable code while rejecting similar secure controls under matched access. The intended unit is a vulnerable/control pair, with target detection and control rejection reported separately. The documentation proposes four seed families (SQL injection, authorization/IDOR, business workflow, and token scope), two prompt conditions (`direct` and `attack_path`), repeated runs, source-level control-purity review, and local hidden oracles.

This contributes directly to the future stopping study in one way: it recognizes that apparent success must be verified independently and that a plausible report is not enough. It does **not** establish a measurement of what an agent does after negative evidence arrives.

### Status of the requested research question

For *When to Stop*, the protocol, controlled nine-task engineering fixture, task and
trajectory schemas, independent finite-state validator, public-task projection,
observable runner, append-only trace/receipt format, and scripted smoke test are now
implemented. They establish an auditable measurement boundary, not empirical evidence.

The following remain **NOT IMPLEMENTED**:

- a reviewed confirmatory task suite with the preregistered 32 families and infrastructure controls;
- approved image-backed local runtime and a passing full container safety gate;
- a provider-backed agent adapter with frozen model/prompt/tool/provider configuration;
- runtime-hidden validator deployment for image-backed tasks and leakage review of that deployment;
- coder calibration and a production version of the strategy/hypothesis derivation codebook;
- power simulation, randomization freeze, result ledger, or any main-study analysis; and
- experimental data, pilot data from a real agent, or any scientific outcome about stopping behavior.

### Documented AVB findings and their boundary

The manuscripts report a narrow finding that target-only recall can conceal failure to reject controls, and later report that several controls were themselves impure. That is a meaningful validity lesson. It cannot be repurposed as evidence that an agent "fails to give up": a control report may reflect a true secondary flaw, an unsupported claim, a dataset defect, a timeout, or a different interpretation of the task. The raw trace is required to distinguish those possibilities.

## Completed Components

The following components are complete enough to be inspected in this checkout, not necessarily complete enough for a publication-scale experiment.

| Component | Audit status | Evidence |
| --- | --- | --- |
| AVB v2 schema, taxonomy, config parsing | Verified | JSON contracts parse successfully. |
| Selected v2 helper tests | Verified, narrow | 6/6 tests passed during this audit. |
| Metadata-only reproduction command | Verified, narrow | `reproduce.sh` completed successfully. |
| Static anonymous-submission checks | Verified, narrow | `make -C submission validate` passed. |
| Manuscript/figure/poster assets | Present | Generated assets are present; they were not regenerated during this audit. |
| Candidate-source registry | Present | Lists GitHub, GHSA, OSV, NVD, SWE-bench-style, and other dataset sources. |
| Basic safety intention | Present in documentation | Local/authorized target language and no-live-target language appear in the protocol. |
| Full AVB v0 artifact and evaluation | **NOT VERIFIED HERE** | Referenced sibling directory is absent. |
| *When to Stop* execution plumbing | Engineering fixture only | Local task/validator/runner/logger fixture exists; no provider-backed episode, containerized task episode, scientific pilot outcome, or analysis exists. |

## Missing Components

### Missing for AVB-Bench v2 operationalization

- **NOT IMPLEMENTED:** live GHSA/OSV/NVD/API acquisition clients and a query-plan manager capable of building a documented 10,000+ repository source pool.
- **NOT IMPLEMENTED:** actual source snapshots, API caches, run manifests, repository checkouts, build logs, test logs, behavioral witnesses, or human-review records.
- **NOT IMPLEMENTED:** a schema-validation stage that rejects invalid candidate records before later pipeline stages.
- **NOT IMPLEMENTED:** sandboxed materialization/build/test jobs; the current `build_validation.py` only proposes common commands.
- **NOT IMPLEMENTED:** a robust provenance, licensing, reviewer-identity, and evidence-retention system.
- **NOT IMPLEMENTED:** similarity/lineage/semantic deduplication beyond exact heuristic keys.
- **NOT IMPLEMENTED:** a release builder that enforces all documented confirmation, leakage, and split gates.

### Missing for the new stopping-behavior study

- reviewed confirmatory task families with prevalidated recoverable, weak-feedback, securely unavailable, and infrastructure-control conditions;
- a hermetic image-backed runtime per episode, including a passing egress/no-secret/no-host-mount safety gate;
- a provider-backed adapter plus frozen model revision, prompts, tool permissions, API/runtime version, and sampling controls;
- runtime validator separation and leakage testing in the actual image-backed environment;
- blinded human annotation or independently auditable production labels for strategy/hypothesis changes;
- power simulation, randomization freeze, exclusion register, and confirmatory collection plan; and
- a version-controlled source baseline and image/dependency provenance ledger.

## Technical Risks

| Risk | Why it matters | Evidence in current checkout | Priority |
| --- | --- | --- | --- |
| No version-controlled project baseline | Files cannot be tied to an immutable revision; history, authorship, and regression provenance cannot be audited. | `git rev-parse` fails; no `.git` directory. | Critical |
| Missing referenced benchmark artifact | Most stated AVB infrastructure and results cannot be rerun or inspected. | README paths and protocol layouts point outside the checkout. | Critical |
| No dependency manifest/lockfile | Writing/build scripts import third-party packages (`python-docx`, ReportLab, Matplotlib, NumPy, Pillow, `pypdf`, `python-pptx`) without a reproducible environment declaration. | No `requirements*.txt`, `pyproject.toml`, or lockfile; `sandbox/images/agent-base.Dockerfile` is deliberately only an unapproved offline-build template. | High |
| No proven containerization/isolation | A fail-closed Docker policy and safety harness now exist, but there is no approved image or passing runtime safety gate; executing any target remains prohibited. | `sandbox/`, `docs/safety.md`, and intentionally empty `sandbox/images/approved_images.json`. | Critical before execution |
| GitHub discovery is not rate-limit complete | It retries 429/5xx but does not act on GitHub's 403 rate-limit/secondary-limit responses or `X-RateLimit-*` headers. | `pipeline/discovery/github_discovery.py`. | High |
| Discovery resume can skip data | The GitHub checkpoint is updated before buffered rows are appended to output. A crash in that interval can resume at the next page without persisting the page's records. | `discover()` checkpoint/output order. | High |
| "Security signal" filter is structurally weak | Merged plain GitHub-search records carry a source label, and `filtering.decide()` treats `sources` as a security signal. This can admit repositories without security evidence. | `merge_sources.py` plus `filtering.py`. | High |
| Input/output contracts are not enforced | The JSON Schema is stored but no pipeline command validates records against it. `build_pair()` can emit null repository fields even though the schema requires URL/key strings. | `schemas/candidate.schema.json`, `pipeline/cli.py`, `pipeline/pairs.py`. | High |
| SWE-style pair semantics are unsafe | `base_commit` is used as `fixed_commit`, although SWE-style records are generic repair examples and base commits are not security fixes by default. | `pipeline/discovery/swe_discovery.py`, `pipeline/pairs.py`. | Critical for ground truth |
| Validation can be asserted rather than evidenced | `triage()` promotes a record based on supplied booleans/confidence and can accept a build/test flag where a behavioral security witness is absent. | `pipeline/validation.py`. | Critical for benchmark release |
| Deduplication is not robust | It clusters exact repository/patch/file/function hashes; it has no fork lineage resolver, normalized-diff similarity, code similarity, or semantic review workflow. Unknown patch values can also over-cluster. | `pipeline/dedup.py`. | High |
| Grouped split is declarative | The split helper hashes a row's existing semantic cluster; it does not construct or verify global lineage/patch/code groups across records, and missing dates can enter the random split. | `pipeline/split.py`. | High |
| Hard negatives are heuristic | The selector uses keyword/file-change signals plus prefilled validation fields, not independent secure-code review. | `pipeline/hard_negatives.py`. | High |
| Build validation does not validate builds | It detects conventional commands but does not materialize, pin dependencies, execute safely, capture logs, or classify real outcomes. | `pipeline/build_validation.py`. | High |
| Test coverage is insufficient for the advertised pipeline | The suite now also covers the public-task boundary, complete in-memory adapter/sandbox/verifier/logger fixture, and no-private-reasoning payload guard. There are still no image-backed integration tests, pagination recovery tests, source-format fixtures, runtime leakage tests, or split-purity tests. | `tests/`, `sandbox/safety_checks/latest_result.json`. | High |
| Script portability is brittle | `render_visuals.sh` hard-codes another absolute path. A direct `shasum` call failed under the current `C.UTF-8` locale during this audit. | Script contents and audit command output. | Medium |
| Manuscript build status is partial | Static submission validation passed, but the stored submission PDF was not rebuilt from a clean, pinned toolchain in this audit. The fallback style is explicitly not venue compliant. | `submission/README.md`, local validation output. | Medium |

## Scientific Risks

1. **Question–artifact mismatch.** The current study asks about vulnerability discovery and secure rejection. The requested study asks about sequential decisions after failure. A success/failure endpoint cannot reveal adaptation without action-level observations.
2. **No stopping construct.** "Give up" could mean an explicit stop, a timeout, a tool failure, a context-window failure, a switch to another hypothesis, or a false final success. Treating these as one label would make the central claim uninterpretable.
3. **No normative evidence model.** Persistence is not inherently irrational: continuing can be correct when feedback is noisy or alternative attack paths remain plausible. Each task must state what makes an observation genuinely disconfirming.
4. **Current AVB negative-control impurity.** The documents report that six controls had additional security-relevant behavior. That makes control-side reports confounded and is a direct warning for any future "failed attack" task labelled impossible.
5. **Inconsistent historical result narrative.** The 15-run versus 144-run conflict makes it unsafe to use existing summary statistics as a baseline until raw records are recovered and reconciled.
6. **No independent evidence for mechanisms.** A transcript may show repeated commands, but it does not by itself prove the model held or abandoned a hypothesis. Interpretation needs an observable event ontology, task evidence, and preferably blinded coding.
7. **Confounding by task difficulty and feedback quality.** A hard task may produce more retries simply because it has more viable paths; a verbose error message may cause apparent adaptation without any general capability difference. Task family, signal reliability, tool affordance, and initial plausibility must be controlled or modeled.
8. **Timeout is a censoring mechanism, not a choice.** A hard wall-clock/token cap can fabricate "persistence" or "failure to stop". Agent-initiated termination, platform termination, transport failure, and budget exhaustion must be separate outcomes.
9. **False-success claims need a separate endpoint.** An agent claiming success without reproducible evidence is different from persisting after failure. Both need deterministic validators and must not be collapsed into one score.
10. **Pseudoreplication risk.** Multiple attempts, repeated runs, transformed presentations, or adjacent fixes are nested observations, not independent failed attacks.

## Security Risks

### Current state

The current metadata-only path is comparatively low risk: it does not clone or execute targets by default, and its GitHub token is read from an environment variable rather than hard-coded. The research protocol also states local/authorized targets only. These are positive design intentions.

The enforcement layer is now **partially implemented but not yet verified**: `sandbox/`
contains a fail-closed Docker policy, pre-start inspection, explicit no-network/no-mount
configuration, resource limits, bounded logs, and cleanup checks. `agent/` adds an
evaluator-owned public-task boundary and a no-process/no-network finite-state fixture;
it does not replace the Docker gate. The immutable image allow-list is intentionally
empty and its runtime suite must pass before any target is executed. Future repository
builds, agent tool use, or exploit reproduction must not run directly on the host merely
because the repository is public.

### Required safeguards before any executable study

- only local, authorized, intentionally vulnerable, or historically reproduced targets;
- disposable container/VM per run with no host credentials, no user home mount, and no access to parent directories;
- default-deny network egress, with a documented exception only for a controlled local service;
- pinned image digest and package cache; no live dependency installation during scored runs;
- read-only benchmark source and separately mounted, write-limited work directory;
- CPU, memory, process, disk, and wall-clock limits;
- a strict command/tool policy and an audit log of every allowed tool action;
- redaction and retention rules for prompts, traces, private evidence paths, and tokens;
- legal/license screening before redistributing source snapshots or advisories;
- an independent safety sign-off before enabling local behavioral validation.

The pending deep security review may identify additional code-level issues; it must be incorporated only after it completes and is independently checked.

## Reproducibility Risks

| Risk | Consequence |
| --- | --- |
| No Git repository or release tag | No exact source revision, diff, or provenance chain for this audit or later results. |
| Missing sibling artifact and raw logs | Reported outcomes, model configuration, prompt hashes, oracles, and exclusions cannot be recomputed. |
| No dependency lock/container | Same scripts may render differently or fail across machines; package/API changes are uncontrolled. |
| Dynamic external APIs/models | GitHub results, advisory metadata, hosted model behavior, and CLI behavior can drift without cached inputs and model snapshots. |
| No raw v2 data | Candidate counts, filtering loss, source queries, exclusions, and status changes cannot be audited. |
| Schema not executable in pipeline | Invalid or incomplete records can silently reach later stages. |
| Inconsistent manuscript status | Readers cannot identify which document is authoritative for the experimental state. |
| Sparse tests | Static and in-memory fixture tests do not establish image-backed end-to-end correctness or repeatability. |
| No production trace deployment for stopping | A versioned observable trace contract exists, but no provider-backed, image-isolated trace collection has been validated. |

## Recommended Architecture

Treat *When to Stop* as a new experimental layer, not a rename of AVB-Bench. It may reuse AVB's control-purity and adjudication ideas, but it needs a task model built for sequential evidence.

```text
versioned task registry + ground-truth packet
             |
             v
isolated per-episode runtime <--> frozen agent configuration
             |
             v
append-only action/observation trace + deterministic validators
             |
             v
blinded strategy/evidence annotation + quality checks
             |
             v
episode-level analysis dataset + preregistered statistics
             |
             v
paper tables/figures + reproducibility release
```

### Core components

1. **Task registry.** A versioned manifest for each local authorized task: initial state, permitted tools, intended goal, known solvability class (`solvable`, `securely_unsolvable`, or `ambiguous/not confirmatory`), deterministic validator, reference reasoning/evidence map, task family, seed, and safety constraints. Do not use an unreviewed "impossible" label as ground truth.
2. **Failure-feedback contract.** Predeclare which observations are diagnostic, how reliable they are, and what alternative paths remain. A task should make a hypothesis *less plausible* through an observable, independently verified signal rather than an arbitrary grader message.
3. **Frozen agent runner.** Record model revision, provider/CLI version, system/task prompt hashes, tools, permissions, temperature/decoding controls where exposed, token/wall/tool budgets, run seed/order, environment image digest, and collection time. The runner should distinguish an agent finalization from infrastructure termination.
4. **Hermetic range.** Run one task episode in a disposable, local environment. The validator must be separate from the agent-visible workspace and must not leak the answer through filenames, logs, or error text.
5. **Trace schema.** Record ordered actions, observations, tool results, command exit status, validator state, declared hypotheses when the condition asks for them, explicit stop rationale, final claim, and a redacted evidence pointer. Do not infer a strategy change solely from natural-language narration.
6. **Verifier and adjudication layer.** Independently verify each claimed success; label unsupported final success, valid success, valid failure, infrastructure failure, and unresolved outcome. Blind human coders should assign post hoc strategy/hypothesis categories from predefined criteria, with agreement reported.
7. **Analysis layer.** Build one analysis row per task episode and nested action events. Preserve raw traces, derived labels, codebook version, and all exclusions. Treat task/seed/configuration as clustering units.
8. **Release layer.** Publish a safe task subset, source/image digests, manifests, lockfiles, redacted traces, validator code, analysis scripts, and a reproducibility guide. Keep unsafe or nonredistributable materials out of the release with explicit omission records.

## Recommended Research Pipeline

### 1. Operationalize the phenomenon before building tasks

Define, before data collection:

- **Attempt:** an action sequence intended to test a named attack hypothesis.
- **Negative evidence:** a task-specific observation that independently rules out or substantially weakens that hypothesis under the permitted state and assumptions.
- **Adaptation:** a predeclared, observable change in parameterization, tool, target surface, attack family, or retained hypothesis set after evidence.
- **Maladaptive repetition:** a near-identical retry after conclusive negative evidence, without new task-relevant information or a predeclared reason to revisit.
- **Rational stop:** explicit termination after the remaining hypotheses are exhausted or below a task-defined threshold, while preserving a valid empty/failure conclusion.
- **False success:** a final success claim rejected by the hidden deterministic validator.

The project should not use a single "persistence score" until these labels are proven reliable on pilot traces.

### 2. Construct a balanced task matrix

Use only safe local tasks and deliberately include:

- solvable tasks where recovery after a failed first hypothesis is possible;
- securely unsolvable tasks where a clear local property rules out the attack goal;
- tasks with multiple plausible paths but only one valid path;
- tasks in which feedback is diagnostic versus intentionally weak, while keeping the underlying task matched;
- controls for tool failure, misleading-but-benign errors, and budget pressure.

Every task needs a validator, a reference solution or proof of unreachability under stated constraints, and independent review. Ambiguous tasks belong in an exploratory set, not the confirmatory denominator.

### 3. Instrument before outcome collection

Pilot the logger and validator on scripted traces and harmless dry runs. Validate that the system can distinguish: repeated command, parameter mutation, tool switch, strategy switch, hypothesis retirement, explicit stop, timeout, platform error, and final claim. This is an instrumentation pilot, not the main experiment.

### 4. Freeze a minimal confirmatory design

Pre-register the task set, exclusions, agent configuration, feedback conditions, randomization, budgets, primary endpoint, coding rules, and analysis plan. Use interleaved/counterbalanced task order. Do not tune prompts, tools, or task labels after looking at confirmatory outcomes.

### 5. Collect complete episodes, not only outcomes

Retain every action and observation, including failed transport/tool runs. Score infrastructure failures separately. Repeated runs estimate stochastic behavior but do not create new independent tasks.

### 6. Verify and annotate independently

Use deterministic validators for success claims and blinded annotation for strategy/evidence labels. Report inter-rater agreement, disagreement resolution, coding-version changes, and all unresolved cases.

### 7. Analyze at the correct level

Report task-level outcomes with uncertainty, then trace-level descriptive behavior. Candidate outcomes include:

- probability of explicit agent stop before budget exhaustion;
- actions spent after conclusive negative evidence;
- rate and latency of hypothesis retirement;
- retry identity versus meaningful mutation rate;
- tool/strategy-switch rate after failure;
- revisit rate after new evidence versus without new evidence;
- valid success, valid failure, unsupported success, and unresolved-final-claim rates;
- discrimination between solvable and securely unsolvable tasks.

Use task- and configuration-clustered uncertainty. A hierarchical or mixed-effects model may be appropriate only after the task count supports it. Paired permutation/McNemar-style contrasts apply only to genuinely paired binary endpoints; action counts require a separate, predeclared model.

### 8. Stress-test interpretations

Test alternative explanations: task difficulty, feedback quality, tool affordance, prompt wording, model drift, hidden solution availability, and censoring by budget. Report negative results and do not equate an observed strategy label with an internal model belief.

## Immediate Next Steps

1. **Recover and freeze the previous AVB artifact.** Locate `AI-BugBounty-Blindness-Benchmark`, preserve raw outputs, record its commit/hash, and reconcile the 15-run versus 144-run statements before treating either as baseline evidence.
2. **Create a version-controlled project baseline.** Initialize or restore the intended Git repository, add a clear source-of-truth policy, and do not overwrite the current manuscripts during the pivot.
3. **Decide the relationship between AVB and *When to Stop*.** The recommended choice is a new study/module that reuses AVB's validation discipline but has its own task registry and preregistration.
4. **Write a two-to-four page stopping-study design memo.** Define the constructs, candidate task classes, allowed inferences, negative-evidence rule, and the distinction between stop, timeout, and false success. Do this before implementing the main harness.
5. **Conduct a safety design review.** Approve an isolated local execution architecture and data-redaction plan before materializing or running any untrusted repository.
6. **Specify the trace and validator contracts.** Create schemas and scripted fixtures first; do not collect agent outcomes until they can be deterministically validated and retained.
7. **Repair the v2 pipeline before using it for evidence.** At minimum: schema enforcement, atomic checkpointing, actual rate-limit handling, source-format fixtures, separation of generic SWE repairs from security fixes, verified grouping/deduplication, and evidence-backed confirmation gates.
8. **Keep the deep security review pending.** When it completes, triage its findings separately and update this status only with verified, scoped conclusions.

No main experiment was initiated as part of this audit.
