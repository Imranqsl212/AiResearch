# Implemented mixed-logistic sensitivity analysis

**Status: implemented and tested on synthetic calibration data only.** This is
an optional sensitivity analysis for the [prospective statistical draft](C5_PROSPECTIVE_STATISTICAL_PLAN_20261123.md).
It does not change the primary family-weighted estimator, alpha allocation,
old protocols or frozen planning outputs. No selected historical cohort was
fitted. No real model request or external publication occurred.

## Model and interpretation

The [Python implementation](../analysis/c5_mixed_logistic_20261123.py) uses
`statsmodels.BinomialBayesMixedGLM.fit_vb` with a mean-field variational posterior.
Fixed terms are treatment, named model and prompt, treatment-by-model and
treatment-by-prompt interactions, and precursor condition when it has multiple
levels. Model identities are fixed strata. It includes three Gaussian random
components:

1. A shared family intercept across models.
2. A shared family treatment slope, **independent of the family intercept**.
3. An onset/block intercept nested within family, model and pair ID.

The independent intercept/slope choice fixes their covariance at zero. It is
an explicitly documented implementation of the draft's random-slope sensitivity,
not an unannounced claim to estimate a correlated random-effects structure.
There is no additional family-by-model random intercept; model-specific family
heterogeneity beyond the shared components is an assumption/limitation.
Every model retains the same family labels so shared-family dependence is
represented. For C4/C3 the pair ID denotes the matched task/prompt/repeat block;
for C5 and A/A it denotes the reserved common onset.

The baseline priors are independent fixed-effect `Normal(0, 2²)` and
log-random-SD `Normal(0, 0.5²)`. A separate, prespecified sensitivity uses
SDs 4 and 1, respectively. These scales concern log-odds and log standard
deviations, not outcome probabilities. Never choose the prior producing the
preferred conclusion. Both model settings and their output hashes must be
frozen before prospective fitting.

Returned coefficient intervals are **95% approximate variational posterior
credible intervals**, not frequentist confidence intervals. No p-values are
returned or passed to Holm. Mean-field posterior independence can understate
uncertainty; convergence and smoke tests do not establish interval coverage.
This method is not `lme4` maximum likelihood, a calibrated frequentist GLMM,
a full-covariance posterior, or an MCMC fit. The primary family-level analysis
remains the confirmatory procedure. A `terminal_regression` endpoint from the
current finite reader concerns the joint authored contract; it must not be
relabeled a security-only failure. Separate functionality/security effects
require separately supported endpoint exports.

A conditional log-odds coefficient is not a risk difference. For each named
model the tool also averages predicted probabilities over a balanced prompt ×
precursor-condition grid and integrates the Gaussian random effects. At
binary treatment `t`, the integrated variance is
`SD_family² + t² SD_family_slope² + SD_onset²`. The random components are
independent by specification. Marginal differences use the same posterior draw
for both treatment probabilities and average over the selected grid. This is
a conditional-on-onset, population-random-effects sensitivity target; it does
not equal the primary finite observed-family contrast or an all-task policy
effect. Reached-onset differences across models remain a selection limitation.

Integration uses 60-point Gauss–Hermite quadrature, compared against 120 points
for every posterior draw/grid cell. Maximum absolute disagreement must be at
most 0.0001. The known numerical fixture also agrees with an independent
adaptive integral. Posterior summaries use 2,000 draws from the approximate
factorized Gaussian distribution, seed 20261123; these are not MCMC draws.

## Refusal and missingness rules

The tool requires 4–6 frozen model names, 2–3 prompt names, an explicit selected
pair roster and both branch rows for every reserved pair. Duplicate or omitted
branches, malformed source hashes, unplanned model/prompt identities and
invalid binary values fail validation. A branch is `VALID`,
`TECHNICAL_INVALID` or `UNSTARTED`. The latter two must have explicit null
endpoints, never zero. If either branch is missing, both are removed from the
fit. The audit retains the pair, its reason, scheduled denominator, the known
other branch and equal-family worst/best bounds. No-onset precursors belong
in a separate reach table and do not create artificial pairs.

Each model must retain at least 15 contributing families. All planned
model/prompt/precursor cells used for balanced standardization need at least
one complete pair. Unsupported cells are not silently extrapolated or dropped.
The fixed design must have full rank. Linear-program feasibility checks refuse
complete or quasi-complete fixed-effect separation; all-zero/all-one outcomes
are refused before loading the optional libraries. Gaussian priors can yield
finite numbers under separation, but this tool does not release such a
prior-dominated fit as a validated sensitivity result.

The optimizer uses deterministic starting means/SDs, L-BFGS-B, at most 1,000
iterations, `gtol=1e-7`, `ftol=1e-13`, and a final gradient infinity norm at most
0.001. Failure, nonfinite outputs or quadrature disagreement cause an explicit
refusal. There is no automatic simplification, alternative optimizer search or
post-outcome term deletion. Diagnostic warnings, iterations and residual
gradient are retained in a successful result.

The input declares either `SYNTHETIC_CALIBRATION` or
`PROSPECTIVE_REPLAY_VERIFIED`. Historical/excluded data labels are refused.
Prospective fitting additionally requires explicit `--allow-prospective`.
That flag is an analysis instruction, **not** admission, upstream verification
or consent. The tool validates the supplied roster and source-hash syntax;
it does not independently replay a live experiment or authenticate human
review. Upstream readers must supply verified endpoint rows. Engineering
adapter fragments must not be relabeled eligible to get past this boundary.

## Input contract

Use one contrast and one endpoint across all frozen model strata:

```text
schema_version: c5-glmm-branch-table-v1
contrast: C5 | C4_C3 | AA
endpoint: early_stop | terminal_regression
data_kind: SYNTHETIC_CALIBRATION | PROSPECTIVE_REPLAY_VERIFIED
models: [4–6 exact identifiers]
prompts: [2–3 exact identifiers]
pair_roster:
  - pair_id, model, family, prompt, precursor_condition, pair_source_sha256
rows:
  - pair_id, model, treatment (0 or 1), outcome (0/1/null), validity
```

For C5/AA, precursor condition is C1 or C2 and the source digest binds the
common onset/prefix. For C4/C3, a domain-tagged canonical matched-schedule
binding may be used if it records the frozen plan/task hashes; it is a schedule
match, not a claim of identical candidate bytes. Label that upstream provenance
accurately. Pair IDs are unique within a model. Treatment is false FAIL versus
truthful PASS, C4 versus C3, or A/A branch B versus A, respectively.

## Runnable checks and outputs

Use an isolated Python 3.11 environment with the
[pinned optional dependencies](../analysis/c5_mixed_logistic_requirements_20261123.txt):

```sh
python3.11 -m venv /private/tmp/c5-mixed-env
/private/tmp/c5-mixed-env/bin/python -m pip install -r analysis/c5_mixed_logistic_requirements_20261123.txt
/private/tmp/c5-mixed-env/bin/python -B -m unittest -q tests.test_c5_mixed_logistic_20261123
/private/tmp/c5-mixed-env/bin/python -B -m analysis.c5_mixed_logistic_20261123 smoke \
  --output-directory /private/tmp/c5-mixed-smoke-new
/private/tmp/c5-mixed-env/bin/python -B -m analysis.c5_mixed_logistic_20261123 fit \
  --input verified-glmm-input.json --output-directory /private/tmp/c5-mixed-fit-new \
  --allow-prospective
```

The last command is an example for future admissible data, not a command run
on this project's selected historical samples. Output directories are exclusive
create. Files include `fit.json`, coefficient/marginal/random-effect CSVs and,
for a smoke run, the explicitly synthetic input fixture. The fit records the
analysis source hash, input-content hash, Python/package versions, priors,
quadrature diagnostics, optimizer diagnostics, counts and missingness bounds.

Development used Python 3.11.18 and the exact pinned package versions in a
temporary environment; the repository environment was not changed. The normal
standard-library test run checks input safeguards and reports optional-backend
skips. The isolated run actually executes those backend tests. Statsmodels
imports emit pandas deprecation warnings in this pinned combination; neither
smoke fit emitted an optimizer warning. An optional CI job must install these
packages to exercise the fitting tests; a skipped backend test is not a fit.

## Recorded synthetic validation

The [baseline smoke artifact](../analysis/c5_mixed_logistic_smoke_20261123/fit.json)
and [prior sensitivity](../analysis/c5_mixed_logistic_smoke_prior_sensitivity_20261123/fit.json)
use exactly the same known synthetic dataset: 20 families, four synthetic model
identifiers, two prompts, two precursor origins, 320 pairs and 640 branches.
The data-generating treatment log-odds coefficient is −0.9, family intercept
SD 0.65, independent family slope SD 0.30 and onset SD 0.50. These labels and
numbers describe generated calibration data, not language-model behavior.

Both fits converged. Residual gradient norms were approximately `2.66e-5`
and `6.90e-6`; the maximum 60/120-point integration disagreements were below
`3e-13`. All four marginal point estimates had the negative direction in both
fits. This confirms execution and expected direction on this fixture, not
unbiased estimation, power, confidence coverage or robustness on real data.
The 16 tests cover explicit missingness, insufficient families, historical
exclusion, duplicate/omitted branches, global/complete/quasi separation,
unsupported balanced cells, nonconvergence, independent quadrature and a
known mixed fit. There is no selected-real-cohort GLMM result.

The implementation follows the official
[statsmodels mixed-binomial API](https://www.statsmodels.org/stable/generated/statsmodels.genmod.bayes_mixed_glm.BinomialBayesMixedGLM.html)
and [variational fitting description](https://www.statsmodels.org/stable/generated/statsmodels.genmod.bayes_mixed_glm.BinomialBayesMixedGLM.fit_vb.html).
The documented mean-field posterior approximation is why these uncertainty
intervals remain a sensitivity display rather than the primary test.
