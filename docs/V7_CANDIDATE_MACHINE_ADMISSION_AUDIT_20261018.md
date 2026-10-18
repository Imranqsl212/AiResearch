# Full-catalog v7 machine admission audit — 18 October 2026

**Decision: structurally consistent candidate; zero families scientifically admitted.**
This audit selects the original four families, batches A/B, and the proposed
**v7** batch C. It does not substitute the older v6 batch-C artifacts or convert
excluded pilots into main data. The source revision before this audit was
`6ccacf980138a6d38b263b700da08e020533b12d`; the new audit code and this
report are working-tree changes until reviewed and committed. Reviewer forms
must cite the eventual clean source commit and the exact bytes they inspected.

## Reproducible machine results

```sh
python3 -B -m analysis.admission_review --catalog v7-candidate
python3 -B -m analysis.validate_human_admission_register --catalog v7-candidate
python3 -B -m benchmark.validate_finite_policy_v1
python3 -B -m benchmark.validate_finite_path_v2
python3 -B -m benchmark.validate_finite_replay_v3
python3 -B -m benchmark.validate_finite_race_v4
python3 -B -m benchmark.validate_finite_batch_a_v5
python3 -B -m benchmark.validate_finite_batch_b_v5
python3 -B -m benchmark.validate_finite_batch_c_v7
python3 -B -m unittest tests.test_admission_review tests.test_finite_batch_c_v7 tests.test_human_admission_register -q
python3 -B -m unittest tests.test_finite_batch_a_v5 tests.test_finite_batch_b_v5 -q
```

| Check | Result |
| --- | ---: |
| Full-catalog index/task/proof/public-parity pre-review | 20 families, 100 C1–C5 rows, zero errors; `CONDITIONAL` |
| Exhaustive finite candidate checks in the seven selected validators | 1,790 (40 + 1,280 + 80 + 30 + 140 + 90 + 130) |
| v7 batch C | 8 families, 40 tasks, 130 candidate checks; index SHA-256 `f8fac1b0171152237f2736493b286ef7cca1e853fa1880915a7c2484817c54d1` |
| v7 C3/C4 real same-observation/opposing-output witnesses | 8 families |
| v7 C5 secure-oracle / failed-benchmark-gate examples | 8 |
| Targeted unit tests | 12 + 15 passed |
| v7 independent reviewer register | 40/40 rows pending |
| v7 adjudication register | 20/20 rows pending; 0 recorded admits |

The v7 C1 validator finds 18 modes that fail the *full required-output
contract*: eight unsafe accepts, seven denial-only availability violations,
and three wrong-output KDF modes. These are separate categories. The v7
validator also finds 43 weak-test false accepts across all five conditions.
They are counts inside the authored finite mode language, not observed agent
failures, real-code vulnerabilities, or population estimates.

The full-catalog command now accepts an explicit `--catalog` argument and
records the seven selected index paths in its output. The default remains
`v6-current`, preserving earlier audit reproduction. The v7 reviewer-register
validator uses the same selected v7 index tuple, preventing catalog selection
from silently drifting between the two checks.

## Scientific and release blockers

The [v7 review packet](V7_HUMAN_ADMISSION_REVIEW_PACKET_20261005.md) still
requires two **independent people** to examine each family and a separate
adjudicator to resolve the result. The structural register audit reports
`PENDING_HUMAN_REVIEW`, `scientific_task_admission_granted=false`, and
`main_ready=false`. A program cannot authenticate expertise, independence,
threat-model validity, or signatures.

The remaining v7 construct questions are material: whether full legitimate
request availability belongs in the security criterion; whether the
RSA/Ed25519, shared-record KDF, and deserialization world pairs are coherent;
and whether public mode names and semantics leak the intended answer. The
C3/C4 certificates establish impossibility only for deterministic stateless
modes over the listed worlds and withheld observations. They do not prove that
arbitrary executable repair, durable state, or safe rejection is impossible.

The current [main release matrix](MAIN_RELEASE_GATE_MATRIX_20261005.md)
remains closed on 12/12 conditions, with zero main model calls and zero
eligible main episodes. Admission also needs corpus alignment, final source
freeze, collector/logging evidence, model freeze, pilot replay, and approved
analysis and annotation plans. None of those conditions is changed by this
machine audit.
