# C5 pilot-informed synthetic sensitivity appendix — 5 October 2026

**Status: PILOT-INFORMED SYNTHETIC PLANNING ONLY; NOT READY.** This appendix
uses the completed *excluded* feasibility pilot to bound hypothetical onset
reach scenarios. It does not estimate a treatment effect or calibrated power.
The frozen earlier grid in `v1_power_sensitivity_20261005.json` is unchanged.

## Pilot anchor and scenario limits

Receipt: `experiments/runs/full_catalog_live_feasibility_20261005/run.receipt.json` (SHA-256 `36f91eda1ffeeb07f9c7f705ca128158f913d39e674e750db359f6adbaed556c`). It records
40 assigned precursor slots, 30 valid slots, 10 technical invalidations,
and 14 observed agent-generated oracle-secure onsets in 10 families.
The observed assigned-slot yield **14/40 = 0.35** is a lower bound if an
invalidated precursor could have hidden an onset. **0.60 = (14+10)/40**
is an extreme upper bound requiring all ten invalidated precursors to
have reached onset; 0.50 is an intermediate scenario. These are planning
bounds, not estimates for a future 20-family study.

The pilot's **10/40 = 25% precursor invalidation** is not an estimate of
post-onset branch-pair loss. We show a separate 25% *hypothetical pair-loss
stress*, alongside the original 5% hypothetical loss. Neither is calibrated
to observed C5 fork failures. The 20-percentage-point stop effect is likewise
hypothetical; the pilot contains no randomized C5 paired outcome.

## Simulation

The unchanged `analysis.v1_power_sensitivity.simulate` draws 2,000 datasets
per scenario with seed `20261005`: 20 independent families, 10 precursor
slots/family, at most five onsets/family, a truthful-PASS early-stop
probability of 0.65, default family shifts and branch dependence, and the
predeclared two-sided equal-family paired-difference t rule (α = 0.05).
At least 15 families must contribute a valid pair. A rejection probability
counts nonestimable datasets as non-rejections. The null rows are a simulated
type-I-error check, not evidence that the model is calibrated to real data.

| Reach | Pair loss | P(reject), hypothetical −0.20 stop effect | Mean contributing families | Mean valid pairs | Nonestimable / 2,000 | Null P(reject) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.35 | 0.05 | 0.649 | 19.13 | 61.79 | 0 | 0.053 |
| 0.35 | 0.25 | 0.558 | 18.37 | 48.62 | 10 | 0.049 |
| 0.50 | 0.05 | 0.779 | 19.90 | 80.15 | 0 | 0.048 |
| 0.50 | 0.25 | 0.675 | 19.63 | 63.15 | 0 | 0.055 |
| 0.60 | 0.05 | 0.849 | 19.98 | 87.87 | 0 | 0.043 |
| 0.60 | 0.25 | 0.737 | 19.86 | 69.33 | 0 | 0.048 |

The JSON contains each scenario's full assumptions, rejection count,
Monte Carlo Wilson interval, mean family count, and mean valid-pair count.
Differences across rows include Monte Carlo noise because the existing
simulator derives a separate random stream for each scenario.

**Interpretation:** These rows quantify how a *specified synthetic model*
behaves if onset reach and pair loss take the listed values. They cannot
clear the preregistration's C5 implementation or design gates, substitute
for a matched PASS/false-FAIL pilot across families, or justify an 80% power
claim from the 40-slot feasibility pilot.

Reproduce from the repository root with the sealed, branch-tracked pilot
receipt present: `python3 -B -m analysis.c5_pilot_informed_sensitivity_20261005`
using new output paths; the script refuses to overwrite either output file.
