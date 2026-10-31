# Archived C5 paired regression recount — 2026-11-01

This is a post hoc description of the **excluded engineering pilot**, not a new model run or a main-study result. The cohort contains 14 matched pairs from 10 task families. A 40-slot precursor produced 30 valid episodes, including 14 secure agent-generated onsets; the first pair was selected before the remaining 13 were scheduled.

## What was checked

The script first verifies the archive receipts, source inventory, schedule, paired requests, and secure onsets with the existing audit. It then reads each archived post-onset `ATTEMPT` candidate, checks that the finite evaluator and separate reference modules have the hashes recorded in that pair's preflight, and recomputes both C1 and C5 results. For all 45 submissions (28 truthful-PASS and 17 false-FAIL), the recomputed candidate hash, raw test result, finite security result, and benchmark verdict agree with the recorded event. There were no indeterminate finite results.

“Terminal regression” means the **last submitted candidate** was `INSECURE` under that bounded finite oracle; if an arm submitted nothing after onset, its verified secure onset is used. “Temporary regression” means at least one post-onset submission was `INSECURE`. These labels do not prove general security or capture unsubmitted code.

## Descriptive results

| Outcome | Truthful PASS | False FAIL |
| --- | ---: | ---: |
| Terminal finite-property regression | 5/14 | 7/14 |
| Any temporary finite-property regression | 8/14 | 7/14 |

| Terminal pair outcomes | False FAIL: no regression | False FAIL: regression |
| --- | ---: | ---: |
| Truthful PASS: no regression | 6 | 3 |
| Truthful PASS: regression | 1 | 4 |

The pair-weighted terminal difference is 2/14 (14.3 percentage points) more regressions in false FAIL. Giving each of the 10 families equal weight yields a descriptive difference of 0.15. The temporary-regression contrast points the other way (8 vs 7), and four pairs regress in both arms. These mixed outcomes do not support a general effect claim.

## Protocol boundary

This older C5 runner applied false FAIL **again** to later secure submissions and gave both arms a shared three-decision continuation notice. The newer v7 integrated pilot uses a **one-shot** false verdict at the verified onset. The two protocols must not be pooled as one experiment. This selected, excluded cohort has no population confidence interval, causal effect estimate, or main-study eligibility.

## Reproduce

From the repository root:

```bash
python3 -B -m analysis.c5_paired_regression_recount_20261101 --check
python3 -B -m unittest -v tests.test_c5_paired_regression_recount_20261101
```

The machine-readable result is [`c5_paired_regression_recount_20261101.json`](c5_paired_regression_recount_20261101.json). The script recomputes that JSON from archived candidate records and stops if the tracked result differs.
