# Exact family-sign sensitivity for the minimum study design

**Status: ILLUSTRATIVE PLANNING ONLY.** This calculation contains no pilot or main agent outcomes, does not implement the preregistered GEE, and does not clear a power or READY gate. The [machine-readable calculation](../analysis/family_sign_sensitivity_20261004.json) comes from [stdlib code](../analysis/family_sign_sensitivity.py).

## Setup

The master's minimum design has 20 independent task families, four core conditions, and five fresh runs per condition: 400 core episodes. For one matched directional contrast, average the repeated outcome within each arm and family, take the sign of the paired family difference, and count positive signs. This yields at most **20 independent signs**, after excluding zero differences. The examples below assume all stated families are non-tied. Illustrative contrasts could compare C2 with C1 on repair, C4 with C3 on stopping, and R1 with R0 within the same task stratum; RAG arms would require additional episodes beyond the 400 core episodes. No actual contrasts, endpoints, directions, or multiplicity family are frozen here.

Under a sign-symmetric null with independent families, the one-sided exact sign-flip tail is `sum(comb(n,j), j=k..n) / 2**n`. Under a hypothetical common family concordance probability `q`, the chance of crossing a fixed cutoff is `sum(comb(n,j) * q**j * (1-q)**(n-j), j=k..n)`. Both are evaluated as exact rational numbers before decimal display. Effect magnitudes are deliberately ignored.

## Multiplicity illustration at 20 non-tied families

For an *illustrative* family of three one-sided secondary contrasts with familywise alpha 0.05, Holm's ordered thresholds and attainable sign cutoffs are:

| Ordered p-value rank | Holm threshold | Minimum positive families | Attained null p (exact fraction, rounded decimal) |
| ---: | ---: | ---: | ---: |
| 1 | 1/60 (0.016667) | 16/20 | 1549/262144 ≈ 0.005909 |
| 2 | 1/40 (0.025000) | 15/20 | 5425/262144 ≈ 0.020695 |
| 3 | 1/20 (0.050000) | 15/20 | 5425/262144 ≈ 0.020695 |

At the first step, 15/20 gives p = 0.020695 and misses 0.05/3; 16/20 gives p = 0.005909. This strict first-step criterion is sufficient for a given contrast to be rejected by Holm regardless of the dependence between contrasts. Later ranks can use their larger thresholds only if earlier ranks pass. If seven contrasts are chosen instead, the first threshold is 0.05/7 and still needs 16/20 because the attainable p-values are discrete. The real multiplicity family must be frozen before main outcomes are inspected.

## Exact sensitivity under hypothetical concordance

The table gives the chance that **one** contrast meets the conservative 0.05/3 first-step cutoff. `q` is the probability that an independent non-tied family favors the predeclared direction; these values are planning scenarios, not pilot estimates.

| Non-tied families | Positive cutoff | q = 0.60 | q = 0.70 | q = 0.75 | q = 0.80 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 15 | 13/15 | 0.027 | 0.127 | 0.236 | 0.398 |
| 20 | 16/20 | 0.051 | 0.238 | 0.415 | 0.630 |
| 30 | 22/30 | 0.094 | 0.432 | 0.674 | 0.871 |
| 40 | 28/40 | 0.129 | 0.577 | 0.821 | 0.957 |

The 15-family row represents five tied or otherwise unusable family contrasts out of a scheduled 20; it is not a missingness model. With q = 0.70 and 20 non-tied families, this simple sign-only rule has rejection probability 0.238 for one contrast. This is a different, less information-rich rule than the existing family-t planning proxy and cannot establish the actual GEE's power or the joint power of several hypotheses. The 30- and 40-family rows show how this specific sensitivity changes if independently reviewed families are added.

## Why five repeats are not 100 families

Repeats can make each family's arm averages more stable, reduce ties, and reveal within-family variation. They do not create new independent task families. For example, suppose 16 of 20 family contrasts are positive and each sign repeats identically five times. The correct one-sided family p is **0.005909**. Treating the copied signs as 80 of 100 independent signs would report **5.58e-10**, severe pseudoreplication. The example is hypothetical, not an observed result.

## Limits and use

Independent, sign-symmetric families and a common q are strong assumptions. Ties, unequal family effects, outcome-dependent missingness, flawed security oracles, incomplete failure exposure, model drift, and cross-contrast dependence can change operating characteristics. A sign test also throws away effect magnitudes. These numbers motivate evaluating whether the minimum 20-family design is adequate, rather than declaring a required sample size. Freeze the real estimands, multiplicity family, GEE decision rule, and plausible data-generating scenarios; then simulate that exact rule before main collection. Additional repeats cannot substitute for additional independent families if that power gate fails.

## Reproduce

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_family_sign_sensitivity -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m analysis.family_sign_sensitivity --check
```

Source SHA-256: `259d4e3bb6dfa19a94d1102903ebe5d88a64b9e0ca3de964a39b59384bd89fa7`.
