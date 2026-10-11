# Excluded C5 raw fixture reader — 5 October 2026

[`analysis/c5_raw_archive_reader.py`](../analysis/c5_raw_archive_reader.py)
provides a read-only bridge from the excluded C5 fixture archives to a paired
family diagnostic. It makes no provider call and writes no result file. Its
output always says `phase=pilot`, `eligible_for_main_analysis=false`,
`main_dispatch_allowed=false`, `model_calls=0`, and
`semantic_oracle_verification=false`.

The caller supplies the proposed plan, **one allocation directory per family**,
and matching pair and precursor trace directories for each archived selected
pair. A selected onset without a complete pair archive needs an explicit
structured entry in `missing_pair_reasons`; it remains an invalidation with no
behavioral difference. Unused reservations and the sixth or later secure onset
are retained as nonreach and exploratory overflow respectively. The reader
does not substitute later onsets for invalidated pairs.

For every archived selected pair, the reader runs the existing
`verify_excluded_pair` and `verify_excluded_precursor_link` contracts, checks
the exact plan bytes and full family onset prefix, and then parses the archived
assistant action from each exact response file. It derives decision counts,
candidate submissions, distinct new candidate hashes, exact onset-candidate
resubmission, early voluntary stop, and the paired `false FAIL − truthful PASS`
differences. Each archived pair row retains the pair and precursor receipt
hashes plus the selected request and response hashes. A voluntary stop at
decision three is **not** early. Timeout is a
valid zero for that endpoint; a pair with an invalidated arm has no paired
difference. For each family with at least one valid pair, `D_f` is the mean of
its preselected valid paired early-stop differences. A family with no valid
pair has `D_f=null`.

The numerical check uses one `D_f` per contributing family. With fewer than 15
valid-pair families, or zero between-family variance, the test is marked
nonestimable and has no p-value. Even if 15 or more varied fixture families
were supplied, any calculated t statistic is labeled
`EXCLUDED_FIXTURE_T_DIAGNOSTIC_ONLY`; it is never a main result.

Focused tests:

```bash
python3 -B -m unittest -v tests.test_c5_raw_archive_reader
```

The tests cover exact-byte action counts, a negative `D_f` sign example,
first-five onset selection and sixth-onset overflow, archived and unarchived
invalidations, tampered selected receipt/response bytes, and a mismatched
precursor despite individually valid archives.

## Remaining scientific limits

These archives are scripted fixtures. Hash and shape verification does not
prove that a model generated the precursor or continuation, that the supplied
oracle verdict is true, or that the original request preceded any live network
dispatch. Precursor slots without selected pair archives are represented by
allocation statuses here, not independently replayed full traces. The caller-provided
missing-pair reason is not itself an immutable signed receipt. These limits
prevent use of this reader as a main collector or a confirmatory analysis
release, even when every local validation passes. Human admission, independent
oracle/proof replay, live provenance, blind coding and the final main gate
remain separate requirements.
