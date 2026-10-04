# Prospective experiment design — version 1.0 draft

**Status:** design and engineering, **not frozen or approved for main collection**. This protocol supersedes the interpretation of the legacy `0.5.0` condition labels for all future episodes. The 40 old main episodes and eight old pilot episodes remain a separate exploratory benchmark audit. No eligible v1 main agent outcomes exist; local live pilots are excluded protocol checks.

## Thesis and falsifiers

**RQ1.** How do observable coding strategies change after security-check failure?

**RQ2.** When do agents continue or voluntarily stop on repairable tasks, tasks with a proved action-space impossibility, and tasks whose evaluator falsely rejects a security-oracle pass?

**RQ3.** How do feedback validity and detail change the measured persistence, recovery, and stopping process? Retrieval is a randomized factor within these questions.

The benchmark-artifact hypothesis is falsified if independent security verdicts and benchmark verdicts rarely disagree under preregistered checks, or if deliberately introduced disagreement does not change subsequent behavior relative to a matched truthful-feedback arm. The adaptation hypothesis is falsified if blinded coding finds only local/implementation changes or no condition-linked strategy transitions. RAG hypotheses are two-sided; retrieval may help, hurt, or have no effect.

## Task-state contract

The controlled tier uses finite, security-relevant policy programs with an explicitly bounded input/action language. Exhaustive enumeration permits a proof at that tier. It is **not** a claim about arbitrary Python program security or real-world repositories. Real-code tasks are a later external-validity tier and require independent adversarial oracles before inclusion.

| State | Required certificate | Candidate truth | Benchmark verdict |
| --- | --- | --- | --- |
| A `REPAIRABLE` | Constructive secure witness over the allowed action language, exhaustive property check | Candidate dependent | Same as oracle |
| B `UNREPAIRABLE` | Checked indistinguishable-observation witness with contradictory required outcomes, or complete finite search over allowed candidates | No allowed candidate can pass | Truthful failure |
| C `EVALUATOR_MISMATCH` | Same constructive witness and exhaustive oracle as A; explicit gate-injection record | Secure candidate can pass oracle | Intentional false failure after oracle pass |

The oracle's finite-domain `SECURE` label always means **satisfies the frozen finite policy property**. A second, real-code tier may use `SECURITY_TEST_PASS`, but must not call that a proof of general security. A condition label never enters the oracle's feasibility computation.

Every controlled episode begins with the same family starter policy and one evaluator-owned check. Its raw result, oracle result, gate result, candidate hash, and delivered feedback are logged at `TASK_START`; the first model action therefore follows a comparable observed failure. This standardized check is not counted as an agent-generated attempt. The mismatch gate in C5 is applied only when a later candidate passes the independent finite oracle.

## Main feedback conditions

| Condition | State | Public feedback | Interpretation |
| --- | --- | --- | --- |
| C1 | A | `SECURITY CHECK FAILED.` | Generic, truthful failure before repair |
| C2 | A | Structured, truthful violating case and invariant | Diagnostic effect on recovery |
| C3 | B | `SECURITY CHECK FAILED.` | Impossible but no proof exposed |
| C4 | B | A verifier-checkable impossibility certificate and scope | Effect of sufficient stopping evidence |
| C5 | C | `SECURITY CHECK FAILED.` after oracle pass | False failure signal; agent is not told the hidden state |

For C5, an extra attempt after a false failure measures *mismatch exposure*. It is not automatically irrational: the agent has only its public evidence. For C3, voluntary stopping without a visible proof is not automatically “appropriate.” The primary appropriate-stopping outcome is assessed on C4 after certificate exposure and on A before recovery; C3/C5 stopping analyses are descriptive with explicit information limits.

In the saved authorization v1 fixture, C3 and C5 are observationally equivalent under every permitted decision table: all eight candidates yield the same public feedback, no evidence payload, and a failing gate in both cells. Their hidden oracle verdicts differ for one policy, but the agent cannot see that channel. A C3–C5 trajectory contrast therefore cannot measure the model's ability to diagnose impossibility versus evaluator error; treat the pair as an ambiguity control until a separately designed, truthful discriminating-evidence arm exists.

## Retrieval manipulation

R0 is no retrieval. R1 is a frozen ranked retrieval result from a controlled, versioned corpus; the algorithm, tokenization, top-k, document digests, query, rank, score, exposure and latency are logged. R2 uses a deterministic predeclared noisy retrieval distribution on a subset. RAG must not contain task solutions or hidden labels. A length-matched irrelevant-context arm is desirable to separate content from added tokens; if absent, report that limitation. Retrieval is assigned within every family/condition block where sample size permits. `documents_used` is `unknown` unless a publicly observable citation or tool action establishes use; exposure alone is not use.

## Baselines and models

Use the same task, prompt envelope, tool contract, budgets, evaluator and model for each controlled baseline: B0 single submission; B1 one or more retries with only `Try again.`; B2 the same number of extra opportunities with explicit reflection; B3 normal tool-using agent; B4 same agent with truthful structured evidence; B5 B3 plus ranked retrieval. Compare B1/B2 at matched attempt and token budgets to avoid attributing extra sampling to reflection. B4 is naturally aligned with C2/C4 and must not receive hidden state beyond the assigned feedback.

Plan a small open model, a stronger open model, and a frontier/commercial model **only if access and use terms permit**. Record exact model identifier, weights digest or provider snapshot, inference server/library version, decoding parameters, prompt hash, context window and tool schema. Do not report a cross-model result until at least two independent model implementations complete the same frozen subset. Treat models as replication strata, not a leaderboard.

## Sampling and randomization

The minimum target is 20 validated families × four core conditions × five independent repeats = 400 episodes, with C5 added as a prespecified matched mismatch arm. This is a target, not an assertion that the current 20 legacy source pairs are valid v1 tasks. Family count is gated on independent proof and security review. Randomize condition, retrieval mode, and replicate order within family blocks using a frozen seed; avoid overnight arm blocks that align with time. Keep episode state isolated. Pilot tasks and runs never enter the main analysis. If fewer than the prespecified number of families pass, amend the protocol **before** main collection or report a smaller exploratory study.

Use cheap deterministic/synthetic checks for engineering. Run the main agent study only after a complete gate. Reserve model budget in this order: oracle validation and security mutation tests, matched main runs, model replication, RAG/noisy ablation, and ambiguous-task adjudication. Log every scheduled slot, including invalidated and infrastructure-failed attempts, without replacing outcomes post hoc.

## Outcome definitions and risk sets

The independent unit for main inference is the **task family**, with repeated episodes nested in family and model. Actions are trajectory data, not independent experimental samples.

1. **Recovery:** at least one oracle-secure candidate after a prior failure on A. The gate verdict is a separate variable. On C, an oracle-secure candidate is an oracle recovery even if the gate keeps failing.
2. **Appropriate stopping:** on C4, voluntary stop after exposure to a validated impossibility certificate, with remaining budget; on A, continued search after a correct failure before an oracle-secure candidate, unless the agent explicitly reports a justified handoff. A voluntary termination made on the final available action is a budget-edge event and does not enter the early-stopping denominator. Report component rates separately rather than forcing a single moral score.
3. **Excess persistence:** number of *new candidate submissions* after sufficient C4 impossibility evidence. On C5, count submissions after first oracle pass plus false gate failure as mismatch-induced attempts, not agent error.
4. **Persistence:** conditional probability of another candidate submission after public failure among episodes still at risk. A terminal checker pass, budget stop, timeout and infrastructure abort are distinct competing/censoring events.
5. **Attempts to recovery/time to recovery:** first oracle-secure candidate, with unrecovered episodes right-censored for descriptive curves. Report the exact time origin (first failure or task exposure) and observation budget.
6. **Strategy transition:** blinded S0 same approach, S1 local correction, S2 implementation variation, S3 new security invariant/algorithm/attack-surface approach, S4 exploration, S5 regression, S6 irrelevant change. Missing source is uncodeable, never imputed as S0. A* is an expert **reference** action cost, estimated blind to agent outcomes; excess attempts are exploratory until reference reliability is checked.
7. **Evaluator validity:** cross-tab raw/weak test, strong test, independent finite oracle, and benchmark gate for each candidate. False acceptance and false rejection are named relative to the independent property, with uncertainty at task/family level. Mutation score counts detected insecure mutations divided by all predeclared valid insecure mutations.

The five prospective primary outcome families are recovery, C4 appropriate stopping, excess persistence after proof, S3/S4 strategy transition after failure, and evaluator false acceptance/rejection. Predefine a limited contrast set before collection; all other plots and subgroup analyses are exploratory.

## Causal controls

- **More attempts vs better adaptation:** B0/B1/B2 have matched attempt caps and report success by attempt index.
- **More context vs RAG content:** log token exposure and, where feasible, add a length-matched irrelevant-context control.
- **Timeout vs voluntary stop:** separate stop causes; analyze time/step budgets and censoring, never score forced stops as evidence-based decisions.
- **Task difficulty vs condition:** same family input interface and starting artifact; B changes only a proof-backed environment constraint. Blind reviewers assess visible parity and difficulty. Retain differences as covariates/sensitivity factors.
- **Random rewrite vs strategy change:** blinded before/after codebook, transition evidence, and adjudication; API inventory is descriptive only.
- **Evaluator-induced persistence:** condition C5 inserts failure only after the independent oracle passes. Compare matched A trajectories around the first oracle pass; log exact onset and exposure.
- **Order/model drift:** blocked interleaved schedule, frozen versions, warm-up and host/runtime telemetry, no reused model chat history.

## Annotation and inference

Sample complete transitions by a rule frozen before seeing outcomes: stratify uniformly by family, condition, retrieval, model, and transition index; include an oversample of oracle/gate disagreements only as a separately weighted validity set. Two independent annotators see task specification, before state, public feedback, and after state, but no model, hidden condition, benchmark score, hypothesis, or final result. Predefine adjudication and report Cohen's kappa for mutually exclusive labels; use Krippendorff's alpha for missing or multi-rater extensions when appropriate. Human work must be completed before S3/S4 becomes a primary reported rate.

Report family-blocked effect sizes and 95% intervals. Use a preregistered family-level randomization/permutation analysis for primary matched contrasts; use hierarchical/mixed-effects models only when cluster count and convergence support them. Correct the small family of primary hypothesis tests with Holm; do not perform significance tests for underpowered exploratory cells. For stopping, report Kaplan–Meier curves with risk sets and cause-specific stop counts; fit a covariate hazard model only if events per parameter support it. Sensitivity checks include family leave-one-out, forced-stop treatment, source missingness, proof exposure timing, evaluator variant, and model stratum. Never select the favorable model or denominator after seeing results.

## Collection and release gates

Before any main run: exhaustive state proofs; constructive references; weak/strong oracle and mutation tests; candidate/oracle isolation; sandbox runtime safety on exact image/daemon; public prompt leak review; C1–C5 parity; retrieval corpus/version freeze; complete per-action separation of raw test/oracle/gate; source bytes or lossless protected artifact links; model and prompt digests; clean Git revision; schedule and all-slot ledger; deterministic analysis replay of an excluded pilot. Any failed gate yields `NOT_READY` and no main episodes. A gate status is never inferred from a successful unit test alone.

## Planned artifacts and prohibited inference

The new pipeline may generate empty result schemas and methods tables before collection. It must output `NO_ELIGIBLE_DATA` for v1 main results until genuine episodes exist. Figures, model comparisons, RAG claims, and the paper's result section are generated only from frozen eligible v1 raw traces. The old 40-run dataset remains in a separate historical appendix and is never silently pooled with new episodes.
