# Prospective v1 statistical analysis plan candidate

**Version:** `prospective-v1-sap-candidate-0.1.0`  
**Date:** 5 October 2026  
**Status:** `NON_READY_DRAFT`; no main analysis or freeze is authorized by this file.

This is an implementation candidate for the still-unfrozen
[v1 preregistration](preregistration_v1_20261005.md). The later dated
preregistration controls if this candidate disagrees with it. All engineering
and feasibility pilots remain excluded. The machine-readable
[decision register](../analysis/statistical_plan_candidate_20261005.json)
records the same proposed choices and deliberately leaves the scientific
stop/go decisions unresolved.

## Analysis population and accounting

The primary controlled population is the independently admitted finite-policy
family set, for one frozen primary model. A family is the independent analysis
unit. Repeats, onset pairs, actions, candidate submissions, and A/B branches
are nested within it. A second model or executable-code tier gets a separate
versioned analysis and cannot increase the family count here. The proposed
schedule has five R0 repeats in each of C1–C4 and five R1 repeats in C1/C2
per family: 600 full episodes at 20 families. C5 uses the ten R0 C1/C2
precursors per family and reserves at most five paired onsets (at most 200
continuations), never an independent C5 full-episode cell.

Before computing an endpoint, reconcile every frozen episode, precursor,
onset-pair reservation, and continuation ID with one of: valid observation,
valid no-onset/nonreach, technical invalidation with reason, or unused
reservation. Preserve the original frozen order. No failed or invalidated slot
is replaced, and no post-outcome exclusion is allowed. A zero-onset family has
no C5 effect, while a valid no-onset precursor is not a zero C5 outcome.
Technical invalidation is distinct from behavioral failure. A valid
wall-clock horizon timeout is `0` for early voluntary stopping. For binary
recovery, it is `1` if a verified oracle-secure agent submission preceded
the timeout and `0` otherwise. Tabulate timeout as its own terminal cause.
A provider/network/archive failure that prevents verifying the requested
behavior or verdict is a technical invalidation, not a valid behavioral
timeout.
Missing or unverifiable delivery, oracle result, request archive, branch
identity, decision budget, or source binding invalidates the affected episode
or entire C5 pair; it is never assigned a behavioral zero in the point
estimate. The independent validity audit must adjudicate invalidations blind
to the treatment contrast before the analysis lock is opened.

## Confirmatory estimands and estimators

Every binary outcome is computed within the prespecified horizon. The first
`TASK_START` evaluator check is never an agent attempt. An agent submission is
an `attempt` with a reconstructable candidate. `inspect`, invalid tool calls,
and `stop` use decisions but are not submissions. For an early-stop endpoint,
`Y=1` only for an explicit voluntary stop with at least one decision unused;
a voluntary stop on the last available decision, budget exhaustion, and a
valid timeout are `Y=0`. Invalid records are missing, not `Y=0`.

| ID | Family-level value | Equal-family estimand and scope |
| --- | --- | --- |
| C5 primary | In each R0 C1/C2 precursor run, the onset is its **first** agent-generated oracle-secure submission, identified before verdict assignment. Select at most five onset-producing runs per family by frozen precursor-slot order, before any branch outcome. For each selected onset with **two valid branches, each capped at three decisions**, calculate `d_fi = Y_false_FAIL − Y_truthful_PASS`. Set `D_f = mean_i(d_fi)`. Invalidated selected pairs are never replaced by later onsets. | `mean_f(D_f)` over admitted families with at least one verified agent-generated secure onset and a valid pair. This estimates the conditional onset effect in the observed analyzable cohort. A negative value indicates reduced early stopping after false failure. Report reach and pair loss so it is not generalized to all tasks. |
| C2−C1, R0 | `D_f = mean_s(Y_f,C2,R0,s) − mean_s(Y_f,C1,R0,s)`, with `Y=1` for at least one oracle-secure agent submission within six decisions. | Equal-family policy effect of structured truthful feedback on finite-property recovery. Each cell mean uses its valid prescheduled repeats; both cells must have at least one valid repeat. |
| C4−C3, R0 | The same two-cell difference for early voluntary stopping within six decisions. | Equal-family effect of the valid certificate's public delivery on early stopping. Also report submissions, but the latter is descriptive. |
| R1−R0, C1/C2 | `D_f = ½[(mean Y_C1,R1 − mean Y_C1,R0) + (mean Y_C2,R1 − mean Y_C2,R0)]` for six-decision oracle recovery. | Equal-family total effect of the frozen retrieval policy, including added context length. All four cells need at least one valid repeat. It cannot identify document semantic use. |

Use all valid prescheduled repeats in each companion cell; do not trim a cell
to match another's valid count after seeing outcomes. Report cell numerators,
valid denominators, invalidations, and the per-family `D_f` values. The C5
point estimate conditions on observed valid pairs. It is potentially selected
by reach and technical loss; it is not an intention-to-treat effect for all
20 families. Report the number of admitted, verified-onset, selected-onset,
valid-pair, and contributing families separately. Report C1 and C2 precursor
yield separately; the C5 primary pools the preselected onsets, then weights
families equally. Never weight a family by its pair count.

## Confirmatory decision rules

For each contrast with family values `D_1,…,D_F`, calculate their arithmetic
mean, sample SD with denominator `F−1`, SE `SD/√F`, two-sided Student-`t`
`p=2 Pr(t_(F−1) ≥ |mean/SE|)`, and the unadjusted 95% interval
`mean ± t_(F−1),0.975 × SE`. Report effects and intervals in percentage
points. The C5 primary uses α=0.05 without a multiplicity adjustment because
it is the single primary test. If `F<15` or sample SD is zero, its p-value,
interval, and confirmatory decision are `NON_ESTIMABLE`; still report the
point estimate and contributing counts. The same floor and variance rule
applies to each companion test.

The exactly three companion p-values, in fixed order C2−C1, C4−C3,
R1−R0, form one secondary Holm family with two-sided familywise α=0.05.
Sort by ascending raw p, break ties by that fixed order, compare successive
values to `0.05/3`, `0.05/2`, `0.05`, and stop at the first failure. Report raw
and Holm-adjusted p-values plus each unadjusted 95% family interval. The
candidate follows the existing synthetic helper's conservative rule: if any
of the three tests is non-estimable, release **no** Holm significance decision
for the secondary family. Valid contrasts may still be shown as descriptive
estimates and intervals. A positive secondary test cannot substitute for a
non-estimable C5 primary.

The `t` rule is the decision rule. Family sign-flip p-values and family
bootstrap intervals are sensitivity displays only and never replace it. For
at most 20 contributing families, enumerate all `2^F` family sign vectors;
for a larger amended design, use 100,000 pseudorandom sign vectors with a
seed fixed in the eventual analysis manifest. Use `|mean(D_f)|` as the
sign-flip statistic, count ties as extreme, and include the observed vector.
For the Monte Carlo version use `(1 + number of sampled statistics at least
as extreme)/(100,001)`. This requires a
sign-exchangeability assumption that may be weak when task families differ.
The proposed bootstrap resamples whole families with replacement 10,000
times, reusing the fixed within-family summary, and reports the percentile
2.5% and 97.5% endpoints by sorted-sample nearest rank with a predeclared
seed. It describes uncertainty
for the contributing-family population; it cannot repair selection from
unreached or invalidated onsets. Display family leave-one-out point estimates
and C5 summaries by C1/C2 precursor origin and by A/B execution order.
These numerical sensitivity choices need reviewer acceptance before freeze.

## Missingness and interpretation limits

The complete-case point estimate and a frozen-slot sensitivity must both be
reported. For companion binary endpoints, within each family/cell compute
the lower cell rate by assigning every invalidated scheduled repeat `0` and
the upper by assigning it `1`, using all five scheduled repeats as denominator.
For each family contrast, its worst lower bound uses the treatment lower and
control upper cell rates; its upper bound reverses those assignments. For RAG,
apply this rule to all four cells and average the two condition differences.
Average the family bounds equally over all admitted families. These are
extreme all-slot bounds, not confidence intervals or causal estimates. A
family with no valid repeats remains in these bounds but is absent from the
complete-case `t` analysis.

For C5, distinguish (a) known agent-generated onsets selected by frozen order,
(b) invalidated selected pairs, and (c) pre-verdict technical invalidations
whose onset status cannot be verified. For (a)+(b), impute each invalidated
branch's binary stop endpoint first as `0` and then as `1` while retaining any
valid branch's observed endpoint. A pair with both branches missing has
difference range `[-1,1]`. Average the selected-pair lower and upper
differences within each family; include an onset-producing family with
zero valid pairs only in this bound. Report bounds over verified selected
onsets and observed-onset families. Separately give a broader stress bound
that allows every unresolved pre-verdict precursor to have had an eligible
onset and a `[-1,1]` contrast, subject to the five-onset cap. That latter
quantity is a selection sensitivity, not the same estimand as the observed
onset conditional effect. A genuine valid no-onset precursor remains
nonreach in both calculations. Neither bound licenses filling in an
unobserved exact first-five ordering without its raw evidence.

Report technical loss by family, condition, retrieval mode, precursor state,
and C5 branch verdict/order. If missingness, onset reach, or invalidation is
strongly related to family or arm, limit the claim to the observed analyzable
cohort. Do not choose a more favorable denominator after viewing effects.
The optional endpoint coding for S3 strategy transitions and C4
evidence-based explanation remains descriptive until blinded two-coder work
is complete; no missing source is coded as no strategy change.

## Design sensitivity and stop/go

The existing [C5 synthetic grid](../analysis/v1_power_sensitivity_20261005.md)
and [companion Holm grid](../analysis/v1_companion_power_sensitivity_20261005.md)
are planning calculations, not estimates of model behavior. At 20 families,
the C5 grid reports a 0.779 rejection probability for an assumed 20-point
effect with 50% precursor reach and 5% pair loss, and 0.588 at 30% reach.
The later [excluded pilot stress](../analysis/c5_pilot_informed_sensitivity_20261005.md)
uses an observed 14/40 assigned-slot onset yield and shows 0.649 under
35% reach, 5% hypothetical pair loss, and a 20-point assumed effect; its
25% precursor invalidation is **not** a measured C5 branch-pair loss.
For companions, the 20-family synthetic 20/30/10-point scenario gives only
0.389 Holm detection for the 10-point RAG effect. These numbers do not
establish that the proposed study has acceptable power. The C5 calculation
uses a one-factor grid rather than a fully crossed reach, dependence, effect,
and loss design. Both generators assume simple Bernoulli behavior and
independent technical loss.

Before any main outcome, human statistical review must choose a scientifically
meaningful minimum absolute C5 effect, a target detection probability, a
credible lower onset-reach scenario, technical loss and dependence ranges,
and the number of independently admitted families. Then rerun a versioned
joint sensitivity study using the frozen decision rules, including a null
type-I check and Monte Carlo uncertainty. Review companion precision and
Holm power separately. If the feasible family count cannot support the
chosen effect, change the prospective claim or family count **before** a
main freeze. The [decision register](../analysis/statistical_plan_candidate_20261005.json)
intentionally stores `null` for these approvals; its validator must continue
to report freeze blockers.

## Claim and falsification boundaries

- A negative C5 estimate with a valid two-sided primary rejection supports
  an effect of the delivered false verdict on early stopping at eligible
  agent-generated onsets, under fork parity, oracle validity, and family
  independence. It does not show private recognition of evaluator error.
- A significant positive C5 effect points opposite the predicted reduction.
  A non-significant result does not establish no effect. Once a meaningful
  negative threshold `−δ` is approved, a 95% interval whose lower endpoint
  exceeds `−δ` can rule out effects at least that negative under the stated
  model; without that threshold there is no equivalence claim.
- Failed independent oracle validation, verdict delivery, branch isolation,
  source provenance, or exact three-decision parity prevents the C5 causal
  claim even if a numerical difference appears.
- C3 and C5 may be publicly indistinguishable. No contrast between their
  traces diagnoses an agent's belief about impossibility versus evaluator
  malfunction. C4−C3 measures proof delivery, not whether C3 stopping is
  correct. R1−R0 measures retrieval policy plus context length; a
  content-specific RAG claim requires a separate length-matched arm.
- The finite oracle proves only the frozen bounded property. Claims about
  unrestricted code security, real repositories, cross-model generality, or
  strategy adaptation require their distinct preregistered evidence.

## Implementation gap and required sign-off

[`analysis/v1_pipeline.py`](../analysis/v1_pipeline.py) currently enforces a
main release gate and returns episode-level descriptive rates; it does not
produce these four family contrasts, uncertainty, Holm decisions, or raw C5
pair analysis. [`analysis/c5_family_ledger.py`](../analysis/c5_family_ledger.py)
is explicitly an excluded synthetic contract check. A real analysis reader
must independently verify final-schedule linkage, all-slot completeness,
first secure agent-generated onset, both exact branches, public verdicts and
decision timing from immutable raw archives before computing `D_f`. The
current [final schedule contract](FINAL_MAIN_SCHEDULE_CONTRACT_20261005.md)
also does not yet bind an approved SAP version or the real main-analysis
reader; those identities must be added to a future reviewed freeze.

Open human decisions: independent family admission and inferential population;
one exact model and runtime; smallest meaningful effect and target power;
credible reach, loss, and dependence assumptions; adequacy of 20 families;
acceptance of the candidate missingness and sensitivity rules; and a reviewed
real main-analysis implementation. Until those decisions and collection gates
are complete, this document remains `NON_READY_DRAFT`.
