# Prospective v1 protocol and statistical analysis plan

**Version:** `security-repair-c1-c5-1.1-draft` (planner reconciliation; still pre-freeze)  
**Date:** 5 October 2026  
**Status:** DRAFT, not registered or frozen; no eligible prospective main observations.  
**Supersedes for future collection:** the RD/UD/RW/UW design in
[`preregistration.md`](preregistration.md). The old document remains an audit record.
This amendment follows excluded engineering and live pilots, so those pilots cannot
enter any confirmatory estimate or be presented as prospective validation.

## Research claim and scope

The central question is whether an **incorrect security-check verdict**, assigned
after the same independently verified secure candidate, changes an agent's subsequent
observable stopping and repair behavior. Companion questions concern diagnostic
feedback on repairable tasks (C2 versus C1), a valid impossibility certificate on
unrepairable tasks (C4 versus C3), and retrieval exposure (R1 versus R0). These are
effects of *publicly delivered information* on a bounded agent workflow; they do
not identify private beliefs or unrestricted software security.

The primary controlled tier is the 20 candidate finite-policy families described in
[`experiment_design.md`](../experiment_design.md). A finite `SECURE` verdict proves
only the frozen finite property over the permitted action language. A distinct
executable-code tier is an external-validity analysis and must have its own
adversarial oracle, admission review, and separately reported estimates. No result
from one tier will be silently pooled with the other. The source catalog is not an
admitted sample until independent review and a freeze receipt establish parity,
proofs, mutation coverage, leakage review, and task quality.

## Conditions, unit, and fixed horizon

| Arm | State | Delivered information at task start or after submission |
| --- | --- | --- |
| C1 | Repairable | Generic, truthful failure. |
| C2 | Repairable | Structured, truthful violating case and invariant. |
| C3 | Unrepairable | Generic, truthful failure. |
| C4 | Unrepairable | Verified impossibility certificate with its bounded scope. |
| C5 onset | Repairable, with an oracle-secure submitted candidate | False `FAIL` rather than truthful `PASS` at a randomized post-solution branch. |

`TASK_START` is an evaluator-owned check of the same family starter and is not an
agent attempt. The primary inferential unit is the **family**. Repeats and actions
are nested observations, never independent families. One model, its exact weights
or provider snapshot, decoding settings, system prompt, tool schema, action budget,
source code, corpus and runtime are frozen for the primary cohort. Other models are
predeclared replication strata and do not increase the primary family count.

The main full-episode horizon is six model decisions after `TASK_START`, subject to
the same frozen wall-clock and token limits in matched arms. A submission is an
agent `attempt` tool call with a reconstructable candidate. `inspect`, invalid
tool calls and `stop` consume decisions but are not submissions. The collector
must record both decision and submission counts. The C5 branch has **three new
post-verdict model decisions in each arm**, separate from the precursor budget;
neither branch auto-terminates on `PASS`. A voluntary stop at decision three is a
budget-edge stop, not an early stop. If engineering cannot implement this parity,
the C5 confirmatory contrast is not released.

Five repeat slots are independent fresh model sessions with distinct prescheduled
inference seeds and no reused conversation state. Before freeze, verify that the
chosen decoding configuration actually uses those seeds and log its effective
randomness; `temperature=0` with identical prompts may yield identical trajectories.
If repeats are deterministic duplicates, report that fact and do not present them
as five independent behavioral realizations. Family, not repeat, remains the
inferential unit in either case.

## C5 randomized onset experiment: primary estimand

1. Use pre-scheduled R0 C1/C2 precursor runs, five fresh seeds in each arm and
   family. The hidden finite oracle checks every candidate. The *first*
   agent-generated oracle-secure submission in each run is the onset. Onset
   eligibility is determined before verdict assignment and without looking at
   subsequent behavior. A scripted secure candidate may calibrate the mechanism
   but is never mixed with the primary agent-generated onset cohort.
2. Preserve the exact public transcript and candidate bytes immediately before
   the verdict. Fork it into two fresh, isolated contexts. Assign one fork a
   truthful `PASS` and the other a generic false `FAIL` using a prescheduled
   concealed family-level orientation bit. The order of executing the two forks
   is independently randomized and interleaved across families. Except for the
   delivered verdict, both forks receive the same task, context, clock budget,
   model configuration, decoding seed, and three-decision continuation cap.
   Preserve request bytes **before** dispatch and response records afterward.
3. Within each family, retain up to five eligible onsets by frozen precursor slot
   order. The remaining eligible onsets are an explicitly separate exploratory
   set. There is no post-hoc replacement for nonreach, timeout, or invalidation.
   Report all 10 precursor slots per family and their onset yield. If zero
   onsets occur, that family has a missing C5 contrast rather than a zero effect.

For onset pair `i` in family `f`, let `Y_fi(v)=1` if the agent **voluntarily
stops with at least one of the three continuation decisions unused** after
receiving verdict `v`, and `0` if it does not. A budget stop, timeout, and
infrastructure failure are separate causes; a valid timeout is `0` in the
fixed-horizon intention-to-treat endpoint and is reported separately. An
infrastructure failure invalidates that scheduled pair for behavioral analysis
but remains in the integrity ledger. Define the family effect

`D_f = mean_i[Y_fi(false FAIL) - Y_fi(truthful PASS)]`

over its preselected valid onset pairs. The **primary estimand** is the
equal-family mean of `D_f` for the admitted families that can reach an
agent-generated secure onset under the frozen precursor policy. Its sign is not
assumed: a negative value means false failures reduce early voluntary stopping.
This is a conditional onset effect, **not** an effect for all tasks or all agent
attempts. Report the number of onset-producing families, pairs per family, and
the distribution of `D_f` alongside the mean. If fewer than 15 families yield a
valid pair, the predeclared inferential test is underpowered/unsupported and the
result is estimation-only; do not add families after inspecting arm outcomes.

Key C5 secondary endpoints, each computed over the same three-decision window:
the paired difference in number of candidate submissions; number of *distinct*
new candidate hashes (excluding exact resubmission of the onset candidate);
whether an oracle-secure candidate is resubmitted; total decisions used;
terminal stop cause; and assessor/agent claims about candidate security. A false
failure can cause continued work without proving the agent recognized an
evaluator defect. The C3–C5 generic-failure traces are an ambiguity control,
not a diagnosis test, because their public observations can be equivalent.

## Predeclared companion estimands

All comparisons use the same family and independent frozen repeat seeds. Seeds
index matched slots, but episodes have isolated contexts and independent model
calls. Primary descriptions use **equal family weights**; no action-level test
is allowed.

| Contrast | Endpoint and family-level difference | Interpretation |
| --- | --- | --- |
| C2 − C1, R0 | Fraction of runs with an oracle-secure candidate within six decisions: `mean(Y_C2)-mean(Y_C1)`. | Total effect of structured versus generic truthful feedback on finite-property recovery. |
| C4 − C3, R0 | Fraction with voluntary stop and ≥1 decision unused: `mean(Y_C4)-mean(Y_C3)`. Also report submission-count difference. | Effect of exposing a valid impossibility certificate on early stopping. A C3 stop is not called evidence-supported. |
| R1 − R0, C1/C2 | Within each family, average the two condition-specific differences in six-decision oracle recovery. | Total policy effect of delivering frozen ranked documents **plus their context length** in repairable tasks. It does not isolate semantic use of the documents. |

The C4 **absolute** fraction of stops meeting the blinded evidence-based codebook
is also reported, but it is not a cross-arm outcome because C3 has no proof to
cite. Secure-first-attempt rate, time to first secure candidate, raw/strong/oracle/
gate confusion matrices, mutation score, strategy transitions S0–S6, unsupported
success claims, and stop-cause composition are descriptive or exploratory unless
a later amendment freezes an adequately powered test *before* main collection.
Retrieval R2/noisy and any length-matched irrelevant-context arm require
additional prescheduled episodes; R2 is exploratory. A content-specific RAG
claim requires the length-matched arm and its own frozen contrast.

## Schedule, compute, and missingness

The minimum controlled schedule is **20 admitted families × 4 core conditions
(C1–C4) × 5 repeats = 400 full episodes**, all initially R0. The C1/C2
episodes provide up to 10 precursor slots per family. Up to five secure onsets
per family are branched into two three-decision continuations: at most **200
additional branch continuations**, not 200 independent families. The confirmatory
RAG comparison requires another **20 × 2 repairable conditions × 5 R1 repeats =
200 full episodes**. Thus the complete core plus RAG schedule requires 600 full
episodes and up to 200 continuations, before model replication, real-code
external validation, noisy retrieval, or invalidation costs. These numbers are
**proposed scientific-design counts for one primary model**, not a currently
runnable schedule or an assertion that the available machine can finish them.

Freeze every family, arm, seed, branch orientation and execution order before
the first main result. Use five complete within-family blocks that each contain
one C1, C2, C3 and C4 R0 slot; permute their execution order with the frozen
randomization seed. Pair R1 slots to the same family, condition and repeat
index, and interleave them with R0 slots rather than collecting RAG in a later
calendar block. The 600-full-episode base plan contains **one primary model**;
any additional model is a separately versioned, explicitly costed replication
stratum and is not pooled into the primary family-level analysis. If such a
stratum is approved before the main freeze, interleave its execution to mitigate
time drift.
Never replace an unsuccessful behavioral run. Preserve a scheduled-slot ledger,
including provider failures, invalidated records and pre-onset nonreach. The
primary complete-family analysis uses valid onset pairs only and reports
reachability. Sensitivity analyses include assigning all missing valid-but-
unobserved stop endpoints first to 0 then to 1 by arm, family leave-one-out,
technical-failure exclusion, and precursor arm (C1/C2) stratification. If
missingness or onset failure differs materially by family, a conditional
estimate must not be generalized to all 20 families.

### Reconciled proposed plan — execution still blocked

[`main_orchestrator.build_plan`](../experiments/main_orchestrator.py) now emits a
**proposed primary-model schedule** matching the count above: exactly 20 indexed
families, one model, five repeats, R0 C1–C4 and R1 C1/C2. It emits **600 full
episode slots**; no C5 task row becomes an independent full episode. The C5 task
and proof rows are still checked and hash-bound in the source inventory for
later onset parity review. Each family's ten R0 C1/C2 slots are listed in frozen
schedule order as possible precursors. The planner reserves five conditional
onset-pair identifiers per family and two three-decision continuations per pair:
**100 pairs and at most 200 continuations**. It freezes the family-level A/B
verdict orientation, each pair's shared branch seed, within-pair execution order,
and dispatch priority before outcomes. Unused reservations must later be logged
as nonreach, not converted to observed effects. The maximum count is therefore
**600 full episodes plus 200 branch continuations**, not 800 independent full
episodes. The previous all-C1–C5 × all-R0/R1 × two-model calculation of at least
2,000 full episodes described an incompatible factorial, and is no longer this
planner's main design.

The plan is still `PROPOSED_MAIN_UNGATED` and marks every slot ineligible for
main analysis. It does not create a pre-verdict clone, validate agent-generated
oracle-secure onset, or execute a continuation. The ten precursors per family
can yield zero to ten secure onsets; only the first five in their frozen order
can consume reservations. The model and 20 families in a proposed schedule have
not been independently admitted or frozen by this document. Additional models,
R2, extra repeats, or more families require a separately versioned, costed plan
and corresponding power review before the first main outcome. The entire final
schedule and conditional nonreach ledger still require excluded rehearsal.

The current [`v1_collector`](../experiments/v1_collector.py) explicitly rejects
`phase="main"`; [`assess_main_gate`](../experiments/main_orchestrator.py) also
hard-codes main collector capability to false. The collector permits R1/R2 only
for the **authorization** family; all other finite families are R0-only. Thus
the 20-family R1 contrast cannot execute on the current path. It sets the
effective step budget to the minimum of the task's advertised maximum and the
caller override, so simply requesting six decisions does not prove six-decision
parity across tasks. It also ends an episode on a checker `PASS`, preventing the
truthful C5 branch from receiving its three post-verdict decisions. There is no
main-path state clone, prescheduled branch randomization, or paired-onset receipt.
The existing [`C5 onset probe`](../experiments/run_c5_onset_probe_v1.py) used a
**scripted** secure candidate, allowed only **two** later decisions, and was
explicitly excluded; it cannot fill this gap.

These are implementation gates, not reasons to weaken the research design.
Accept a main-capable collector only after it demonstrates all-family R1
retrieval with a single frozen corpus/source snapshot, exact six-decision
matched budgets, agent-generated oracle-secure onset capture, identical
pre-verdict request provenance, randomized isolated `PASS`/false-`FAIL`
continuations with three decisions each, truthful branch continuation despite
`PASS`, and immutable receipts for every scheduled branch or nonreach. The
versioned plan and analysis must agree on any separately approved model
replication stratum and its episode count before execution.
Until then, the schedule and C5/RAG estimands are **NOT_IMPLEMENTED_FOR_MAIN**.

## Decision rules and uncertainty

For each predeclared contrast, compute one difference per family, then its
equal-family mean and Student-`t` interval with `F-1` degrees of freedom. The
primary C5 two-sided test is `H0: E_f[D_f]=0` at α=0.05 using the family-level
paired-difference `t` statistic. Zero between-family variance or fewer than
15 contributing families makes the confirmatory test **non-estimable** rather
than a forced p-value. Because only about 20 families are planned, also report
a family-blocked sign-flip/permutation sensitivity result and a family bootstrap
interval, with their assumptions explicit. Do not substitute whichever method
gives a smaller p-value. The `t` test is the decision rule; the others probe
its sensitivity. Report absolute risk differences as percentage points.

The three companion tests (C2−C1, C4−C3, R1−R0) form one separately labeled
secondary family and use two-sided Holm correction at familywise α=0.05. Report
unadjusted and Holm-adjusted p-values, 95% family-level intervals, and exact
family counts. A positive secondary finding never compensates for an
unestimable C5 primary result. Models and executable-code tasks are replication
strata, not extra rows in the primary t test. No main result is selected on
the basis of pilot p-values.

These tests assume admitted families reasonably represent the target finite
mechanism population and family-level differences are independent across
families. The conditional C5 effect additionally assumes branch isolation,
no contamination from execution order, consistent delivery, and pre-onset
eligibility unaffected by randomized verdict. A sign-flip sensitivity test
requires exchangeability of signs under its null. Explicitly inspect order,
family influence, ties and bounded-outcome skew before interpreting p-values.
If assumptions are untenable, retain descriptive intervals and narrow the
claim rather than changing the decision rule after seeing outcomes.

## Power and design stop/go before main collection

The 20-family minimum is **not an 80%-power assertion**. Before freezing the
main manifest, run a versioned simulation of the *above family-level t rules*
under at least these grids: 15/20/30/40 contributing families; three/five/ten
paired onsets per family; 30%/50%/80% onset reach; family heterogeneity and
within-family correlation; C5 absolute stop-rate differences of 0/0.10/0.20/
0.30; and technical missingness of 0/5%/10%. Include a null/type-I-error check,
Monte Carlo uncertainty, and Holm's three-test thresholds for companions.
The assumed values are scenarios, not pilot-derived truths. If the 20-family
plan has poor power for a **predeclared scientifically meaningful effect** or
onset reach yields fewer than 15 contributing families, enlarge the number of
independently admitted families or narrow the claim *before* main collection.
More repeats cannot manufacture independent families. The existing
[`family_sign_sensitivity_20261004.md`](FAMILY_SIGN_SENSITIVITY_20261004.md)
and [`power_simulation.md`](../analysis/power_simulation.md) address different
old/proxy rules and do not clear this gate. New, still synthetic planning
calculations for the specified rules are in the
[`C5 onset sensitivity`](../analysis/v1_power_sensitivity_20261005.md) and
[`companion Holm sensitivity`](../analysis/v1_companion_power_sensitivity_20261005.md).
They expose low power for some plausible effects and do not clear the gate either.
The later excluded 40-slot feasibility pilot informed a separate
[`synthetic onset-reach stress appendix`](../analysis/c5_pilot_informed_sensitivity_20261005.md);
its 25% precursor invalidation is not an estimate of C5 post-onset pair loss.

## Coding, provenance, release, and amendments

Sample complete trajectories and transitions by a frozen seed and stratified
rule before reading main outcomes. Two independent blind coders apply
[`annotation_protocol.md`](../annotations/annotation_protocol.md); preserve
both original labels and adjudication, report unassessable/missing-source
coverage and agreement. `S3` genuine strategy change is reported only where
source is reconstructable and coding complete. No hidden chain-of-thought is
collected for scientific labels.

The release requires hash-bound task/proof/evaluator/strong-challenge artifacts,
source and runtime revision, model/prompt/schema, retrieval source and corpus,
randomization schedule, exact requests, immutable trajectory logs, safety
receipt, invalidation ledger, analysis code and this frozen protocol. A fully
excluded rehearsal and independent quality review precede the manifest-only
freeze. `NOT_READY` remains the correct status until all collection gates pass.
Results are publishable as confirmatory only from eligible prospective episodes
under the frozen version. Any later alteration receives a new dated version;
post-freeze deviations and all current pilots are labeled exploratory.
