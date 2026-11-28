# Which pairs account for the historical reversal?

The public ledger contains 14 paired continuations across 10 selected task families. Each started from a verified program with a known three-decision limit. After an early stop the recorded final candidate is carried forward. All outcomes below concern the retained candidate's bounded correctness.

## Changes in paired outcomes

Rows give the pair's outcome after decision two and columns after decision three. Each history pair contributes once. A pass refers to the finite reference. The two middle categories identify the feedback arm whose candidate passes.

| At decision two / at decision three | Neither passes | Truthful only | False-failure only | Both pass |
| --- | ---: | ---: | ---: | ---: |
| Neither passes | 4 | 0 | 0 | 0 |
| Truthful only | 0 | 2 | 0 | 0 |
| False-failure only | 0 | 0 | 1 | 3 |
| Both pass | 0 | 1 | 0 | 3 |

In 0/14 pairs, the sole passing arm switched from one side to the other. The paired difference changed in 4/14 pairs across 4 families. Within-family means crossed from strictly positive to strictly negative or vice versa in 0/10 families. The JSON lists the states and contrasts for every pair and family.

## Sensitivity to omitting one family

A positive contrast means more failing candidates under false feedback. The first weighting gives each pair equal weight. The second takes the mean paired contrast within each family and weights those family means equally. Entries are percentage-point differences rounded to one decimal place. The JSON preserves exact fractions.

| Family omitted | Retained pairs | Pair-weighted at 2 | Pair-weighted at 3 | Family-weighted at 2 | Family-weighted at 3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| None | 14 | -14.3 | +14.3 | -15.0 | +15.0 |
| ambiguous_parameters | 13 | -23.1 | +7.7 | -27.8 | +5.6 |
| authorization | 13 | -15.4 | +15.4 | -16.7 | +16.7 |
| counter_race | 12 | -16.7 | +8.3 | -16.7 | +11.1 |
| deserialization_allowlist | 12 | -16.7 | +16.7 | -16.7 | +16.7 |
| dns_rebinding | 13 | -15.4 | +15.4 | -16.7 | +16.7 |
| environment_injection | 12 | -25.0 | +8.3 | -22.2 | +11.1 |
| kdf_salt | 13 | -7.7 | +15.4 | -5.6 | +16.7 |
| nonce_uniqueness | 12 | 0.0 | +25.0 | -5.6 | +22.2 |
| path-boundary | 13 | -15.4 | +15.4 | -16.7 | +16.7 |
| signature_algorithm | 13 | -7.7 | +15.4 | -5.6 | +16.7 |

These deletions measure sensitivity to the composition of the observed cohort. They reuse histories and do not yield independent replications, sampling intervals, or estimates of what an agent would have done under an announced two-decision budget.

Run `python3 -B -m analysis.c5_horizon_sensitivity_20261128` from the repository root to verify both files against the released trajectory ledger.
