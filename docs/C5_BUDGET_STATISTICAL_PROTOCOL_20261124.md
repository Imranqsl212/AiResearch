# Prospective verdict × announced-budget statistical protocol

Status: local prospective draft, 24 November 2026. This is a **separate** experiment from the earlier C5 early-stop primary and the C4/C3 secondary design. It neither registers a study nor grants main-study eligibility. Current selected engineering families and every current capture remain excluded; synthetic calibrations are not model findings. No existing dataset or earlier analysis output is changed.

## 1. Question and primary contrast

Does announcing and enforcing one extra continuation decision change terminal finite correctness differently after false FAIL than after truthful PASS? At the first qualifying secure agent submission, start four separate continuations from the same candidate and pre-verdict history:

| Cell | Initial verdict | Announced and enforced continuation cap |
|---|---|---:|
| PASS2 | truthful PASS | 2 |
| PASS3 | truthful PASS | 3 |
| FAIL2 | false FAIL | 2 |
| FAIL3 | false FAIL | 3 |

Only the initial verdict is manipulated; later checks are truthful. Each arm is generated independently; a PASS3/FAIL3 trace truncated after decision 2 is **not** a budget-2 arm. The treatment includes both the communicated opportunity and the enforced cap, so it does not isolate extra computation from the announcement.

For binary terminal finite correctness Y, the sole primary contrast per model is

`D = (Y_FAIL3 − Y_FAIL2) − (Y_PASS3 − Y_PASS2)`.

D ranges from −2 to 2 for a block. A negative mean means that the additional announced opportunity has a less favorable effect under false FAIL. It does not by itself establish either simple effect, a psychological mechanism, security of arbitrary code, or an optimal stopping rule. The four cell rates, budget gains within verdict, verdict effects within cap, stopping, and decision costs are descriptive secondary displays.

## 2. Selection, units, and proposed sample

A completed, verified six-decision C1 or C2 precursor supplies its earliest agent-issued submission that is secure and raw-test PASS. Selection occurs before continuation treatment. A completed precursor without such a submission is NO_ONSET; a technically invalid precursor is TECHNICAL_INVALID even if an earlier secure prefix was observed. Neither becomes four behavioral zeros. All slots remain in the ledger, without replacement.

Proposed per-model schedule: 19 distinct families × 2 precursor origins × 3 prompt phrasings × 5 repeats = **570 precursor/onset reservations**. Four model identities and versions must be frozen prospectively. A common scheduled branch seed is metadata, not proof that a provider honors seeds or that the four potential endpoints share identical randomness. Counterbalanced execution order must be retained.

The matched onset block is the contrast unit; the family is the aggregation and uncertainty unit. Actions, four branches, prompt variants, and repeated onsets are not independent family replicates. First average block contrasts within each family; then average contributing family means equally. Planned origin/prompt coverage is balanced; realized onset and complete-case composition need not be. Show separate origin and prompt tables and leave-one-family-out estimates.

## 3. Endpoint and stopping definitions

Y is the retained candidate's finite contract label at the actual end of its assigned continuation, including an early completed branch. An indeterminate label is missing, not failure or success. This endpoint is distinct from operational completion and an agent's confidence. It is not automatically a separate functionality/security measure.

Stopping counts use the verified runner's structured, controller-accepted terminal action (terminate or a protocol-defined claim). Unparsed prose does not qualify. Report requested-stop and early-stop counts separately from correctness. Technically invalid branches contribute no behavioral stop indicator even when a controller receipt contains a false default. Decision costs are retained separately.

## 4. Missingness and incomplete capture windows

The complete-case point estimate uses **the same four-cell-complete blocks for every displayed contrast**. This makes the interaction and simple effects algebraically comparable. The estimand of scientific interest remains the mean contrast over observed eligible onsets; complete-case identification requires an explicit assumption that technical loss is unrelated to the relevant outcomes within family. No software flag establishes this assumption. If an entire family has no complete blocks, the point estimate conditions on contributing families; within-family missingness independence alone cannot identify the full equal-family target. Extending that estimate to the omitted families requires a stronger assumption about family selection/completeness. The bounds retain these families without that assumption.

For every selected onset, missing Y ranges over [0,1]. Apply the signed contrast to those ranges, average bounds within each family, and then average families equally. Families with no complete blocks stay in these bounds. Report cell-specific bounds too. These are identification bounds for missing outcomes, not confidence intervals. A precise complete-case estimate cannot remove the uncertainty represented by a bound spanning zero.

Full frozen schedule coverage is mandatory in the reader. Multiple verified, disjoint capture windows may combine only when plan SHA, model, roster, and simulated/observed provenance match exactly. Duplicate block IDs, different plans for the same model, or inconsistent rosters are rejected. Unattempted planned slots remain separate from NO_ONSET and invalid precursors. Partial-window summaries are descriptive; even the optional family-t sensitivity is suppressed until every scheduled slot has been attempted. Reach lower/upper bounds include unattempted and technically invalid precursor slots as unknown. Conditional endpoint bounds apply to the onsets already observed; they do not fill in unidentified future onsets.

## 5. Uncertainty and four-model multiplicity

The optional sensitivity analysis uses a two-sided Student-t approximation over equally weighted family means, with F−1 degrees of freedom. It requires at least 15 contributing families and nonzero sample variance; otherwise the test is not estimable. Report 95% pointwise intervals, explicitly conditional on independent family sampling/aggregation and the missingness assumption. These intervals are not simultaneous four-model intervals. Current hand-selected engineering families do not establish a representative population.

The four fixed model-specific interaction tests form one Holm family at familywise alpha .05. Its first threshold is .0125. Unobserved/nonestimable planned models keep their multiplicity slots; they cannot shrink the hypothesis family. Report all effects, unadjusted p-values, adjusted p-values, missingness bounds, and test availability. The motivating direction is negative; testing remains two-sided. Do not select a favorable model, prompt, or endpoint after inspection. No secondary test enters this primary family, and this protocol does not reuse the older alpha allocation.

The present reader deliberately returns `eligible_for_main_analysis: false` for all supported inputs, including when an optional sensitivity p-value is calculated. A genuine confirmatory release needs the separate scientific admission and registration process, not a CLI option.

## 6. Interaction-specific planning simulation

`analysis/c5_budget_power_20261124.py` specifies all 16 possible four-binary-endpoint patterns, rather than borrowing a two-arm discordance formula. In cell order PASS2/PASS3/FAIL2/FAIL3, marginal probabilities are [.65, .75, .65, .75 + delta], with delta 0, −.10, or −.20. A mixture of independent Bernoulli outcomes and outcomes sharing a uniform variate changes within-block concordance while preserving these marginals. Mixture weights .5 and .9 are sensitivity assumptions, not empirical estimates.

A Dirichlet distribution over the 16 patterns introduces family clustering: concentration `(1−ICC)/ICC` gives the specified ICC of the interaction D, rather than the ICC of any one branch. ICC values are 0 and .2. Every family has 30 reservations; onset reach is .5, independent of D. Independent technical loss .05 per branch gives complete-block probability `.95^4 = .81450625` conditional on onset. Dependence of reach or missingness on potential outcomes is not modeled and remains a limitation.

The simulated test is the same two-sided family-t calculation at the conservative first Holm threshold .0125. Nonestimable repetitions count as nonrejections. This estimates per-model sensitivity-test power, not probability that all four models replicate, power under outcome-dependent missingness, or power of the previous early-stop primary. Synthetic null rejection is reported with alternatives. Wilson intervals quantify Monte Carlo uncertainty only.

| 19 families; mixture .5 | ICC(D) | Rejection probability | Monte Carlo 95% interval |
|---|---:|---:|---:|
| Null delta 0 | 0 | .0116 | [.0090, .0150] |
| Delta −.10 | 0 | .2902 | [.2778, .3029] |
| Delta −.20 | 0 | .8870 | [.8779, .8955] |
| Null delta 0 | .2 | .0086 | [.0064, .0116] |
| Delta −.10 | .2 | .0846 | [.0772, .0926] |
| Delta −.20 | .2 | .3636 | [.3504, .3770] |

These six core rows use 5,000 repetitions each. The remaining 30 sensitivity rows use 2,000 each, covering 19/40/80 families and both concordance settings. For mixture .5 and ICC .2, −.20 interaction power is .7615 at 40 families and .9825 at 80; −.10 power remains .2380 and .4775. Stronger within-block concordance raises power substantially. Thus 19 families cannot be described as generally powered for 10–20 percentage-point interactions. More family diversity can matter more than more calls to the same family.

## 7. Costs and bounded resources

Worst case per model: 570 × 6 precursor decisions plus 570 × (2+3+2+3) continuation decisions = **9,120 decisions**. Four models require at most **36,480 decisions**, assuming one request per decision and no retries. This is not a currency, token, or latency estimate. Early stopping and absent onset can reduce use.

Report actual logged decisions for each cell, with observed-count denominators. For completed branches, policy-completion cost is the actual count. For a technically interrupted or missing continuation, its completion cost is bounded between the known count (or zero) and its assigned cap. These bounds are about an unobserved assigned-policy completion, while logged resource consumption remains an observed accounting quantity. Equal-family cost means, cell bounds, simple contrasts, and the cost interaction are separate from correctness. Cost interaction ranges from −5 to 5 decisions per block.

## 8. Independent historical prefix audit

`analysis/c5_budget_prefix_audit_20261124.py` first reruns the existing archive-integrity and source-identical finite-candidate recount, checks its saved output, and then reads event order. It adds no model calls and changes no historical files. In 14 selected pairs across 10 finite families, all 78 archived decisions are retained. An already completed branch retains its observed terminal state at later prefix displays; no additional decision is invented.

| Observed decision prefix | Truthful correct | False FAIL correct | Equal-family false−truth correctness |
|---|---:|---:|---:|
| 1 | 10/14 | 13/14 | +.20 |
| 2 | 6/14 | 8/14 | +.15 |
| 3 | 9/14 | 7/14 | −.15 |

The observed prefix-2→3 change contrast is −4/14 (pair weighted) and −.30 (equal family). Truthful continuations have eight error-entry events and three recoveries; those three branches finish correct. False-FAIL continuations have eight entries across seven branches and one recovery, followed by relapse; no branch that entered error finishes correct. These are descriptive transitions in post-treatment states, not causal recovery hazards.

All old branches knew the same cap of three, and false FAIL persisted on later secure submissions. Consequently this contrast is **not an estimate of the new announced-budget interaction**. It motivates prospective testing; it does not supply that test's result or calibrate a real-model power claim. Finite-state membership judgments are not reinterpreted as arbitrary-code security.

## 9. Reproducible commands and outputs

From the repository root, create new outputs (existing outputs and sealed captures are protected):

```sh
python3 -B -m analysis.c5_budget_power_20261124 --output-directory analysis/c5_budget_design_20261124
python3 -B -m analysis.c5_budget_power_20261124 --output-directory analysis/c5_budget_design_20261124 --check
python3 -B -m analysis.c5_budget_prefix_audit_20261124 --output-directory analysis/c5_budget_prefix_audit_20261124 --check
python3 -B -m analysis.c5_budget_statistics --run-directory /path/to/sealed-window --output-directory /path/to/new-analysis
```

Repeat `--run-directory` to merge nonoverlapping windows. To request assumption-dependent sensitivity output after complete coverage, add `--assume-independent-families`. To compute the fixed primary multiplicity table, also pass `--planned-model` four times with the frozen identifiers; missing model captures remain explicit. The output binds each input archive-manifest SHA-256, plan SHA-256, and capture count, without treating internal integrity as independent authentication. Output includes `summary.json` and a portable `family_effects.csv`, with provenance flags, cell bounds, stopping counts, coverage, and cost accounting. Output inside a sealed run directory is rejected.

Validation:

```sh
python3 -B -m unittest tests.test_c5_budget_statistics tests.test_c5_budget_prefix_audit_20261124 -q
```

Tests cover interaction signs and ±2 support, unequal family sizes, entirely missing families, individual missing cells, no-onset handling, invalid-branch cost accounting, provenance, full-roster coverage, disjoint-window merging and overlap rejection, four-model Holm slots, synthetic joint moments, deterministic simulation, degenerate nulls, resource budgets, output preservation, and the source-bound historical recount. Runner integration is verified against explicitly simulated captures; it must never be reported as empirical agent behavior.

Completed validation on 24 November 2026: all **35** tests across the two analysis test modules and `tests.test_c5_budget_runner` passed. Full deterministic regeneration of all 36 planning scenarios matched the saved planning files; the historical prefix audit also passed its read-only check. The actual runner→analysis integration used two separately sealed, derived synthetic windows from final calibration v3: 12 captured blocks of the same 570-slot plan, 10 authored onsets, 2 NO_ONSET, and 8 complete four-cell blocks. The 558 unattempted slots remained explicit and optional inference was disabled. Compact provenance is saved in `analysis/c5_budget_integration_20261124.json`. These are software checks, not model experiments.
