# Exhaustive test-set audit of the authored v7 tasks

**Status:** excluded engineering analysis, 4 November 2026. The 8 task
families have not passed independent human semantic admission. Counts below
are *authored task–mode combinations*, not independent model episodes or a
sample of real security programs. Reproduce from the checked-in task bytes:

```sh
python3 -B -m analysis.v7_test_set_sufficiency_20261104 --check
python3 -B -m unittest tests.test_v7_test_set_sufficiency_20261104
```

The [machine-readable full enumeration](v7_test_set_sufficiency_20261104.json)
binds each task to its SHA-256 and records all 78 candidate-mode evaluations
and every nonempty world subset. The [vector figure](../figures/v7_checker_stage_cascade_20261104.svg)
shows the three distinct checking stages.

| Condition | Authored modes | First-world `PASS` | Pass all worlds | Final `PASS` | First-world false positives |
| --- | ---: | ---: | ---: | ---: | ---: |
| C1: repairable | 26 | 17 | 8 | 8 | 9 |
| C3: field withheld | 26 | 8 | 0 | 0 | 8 |
| C5: hidden veto | 26 | 17 | 8 | 0 | 9 |

Thus the *same* C5 catalog has two distinct disagreement sources: nine mode
cards pass the first world but fail the full authored property, whereas eight
pass the full property and are rejected by the hidden acceptance veto. A
single `PASS` or `FAIL` label cannot identify which layer disagreed. In C3,
each family has one mode that passes the first world even though no documented
mode passes all worlds. These numbers are exhaustive over the small frozen
candidate languages, not prevalence estimates.

For C1, the minimum number of authored worlds that reproduces the **full
pass/fail classification of every documented mode** is three for CSRF, two
for six families, and one for KDF salt. CSRF requires all three cases:
`trusted_request` excludes `reject_all`, `cross_site_request` excludes
`token_only`, and `missing_token` excludes `origin_only`. The single
`principal_b` case is sufficient for the KDF salt *mode enumeration* because
only `per_user` emits its expected output on that case. This is not a claim
that a one-case KDF test validates real KDF security.

The first authored world is an intended positive example; its limited
discrimination is unsurprising. The valuable result is the exact layer
decomposition and exhaustive evidence that a first-world pass, a finite
property pass, and final benchmark acceptance mean different things in these
tasks. The local evaluator was cross-checked against the separately
implemented reference function for every mode, but both use the same authored
world facts; neither supplies independent human semantic validation or a
real-world exploit oracle. No p-values or confidence intervals apply to this
deterministic enumeration.
