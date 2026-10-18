# Prospective v1 analysis rehearsal

`prospective_estimands.py` implements the arithmetic in
[`docs/preregistration_v1_20261005.md`](../docs/preregistration_v1_20261005.md)
for the proposed six-cell schedule. `analyze_excluded_archive_bundle` reads every
scheduled `slot_receipt.json` through `verify_excluded_integrated`, which replays
the archived provider responses, finite evaluator/reference checks, and feedback
in the next request. It reads C5 pairs through `audit_excluded_c5_archives`.
The report is always marked `EXCLUDED_FIXTURE_ANALYSIS_ONLY`.
Replay requires the exact frozen source checkout: a later edit to the runner or
evaluator correctly fails source verification until that revision is restored.

The primary C5 quantity is the equal-family mean of the within-family paired
false-`FAIL` minus truthful-`PASS` difference in **early voluntary stop**. A
voluntary stop on the third decision is a budget-edge stop. A valid timeout is
a zero for this endpoint and remains a separate terminal cause. Invalidated
pairs are not replaced; families with no secure onset have no C5 difference.
The planned family-level Student-t decision requires at least 15 contributing
families and nonzero between-family variance. Exact family sign-flip and family
bootstrap intervals are sensitivity calculations, never a choice of whichever
test appears most favorable.

Companion summaries use five scheduled repeats in each C1–C4/R0 and C1–C2/R1
cell. They calculate C2−C1 secure recovery, C4−C3 early stopping, and averaged
R1−R0 recovery over C1/C2. The three p-values receive Holm adjustment only
when **all three** tests are estimable. Missing cell outcomes are shown with
binary worst-case bounds. Descriptive fields retain stop causes, submission
counts, and finite-property regression after an initially secure submission.
`INDETERMINATE` oracle outcomes remain unknown and are counted separately;
they are never silently converted into a confirmed insecure outcome.

`main_release_status()` currently returns `NO_ELIGIBLE_DATA`. The integrated
runner and C5 forks are excluded pilot scaffolds. The original C5 fixture
archive contains candidate hashes but no post-onset oracle checks, so its
security-regression endpoint is not identifiable. The newer
`read_excluded_integrated_c5_pair` replays exact paired continuation archives
with finite evaluator/reference checks after each submission. Its separate
`summarize_excluded_integrated_c5_pairs` output reports false-`FAIL` minus
truthful-`PASS` differences in terminal and any temporary finite-property
regression. `INDETERMINATE` remains unknown, and an invalidated pair has no
paired effect. These are selected **exploratory pilot** pairs; they are not
silently combined with the preregistered C5 estimate. A frozen admitted family
cohort, prescheduled onset allocation, and main-eligible archive reader are
still needed before the causal main contrast can be released.

Run the focused checks with:

```bash
python3 -m unittest tests.test_prospective_estimands -v
```
