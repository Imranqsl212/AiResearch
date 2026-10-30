# Which final candidates can be compared with Bandit? — 30 October 2026

**Status: excluded retrospective measurement.** This audit adds no agent runs,
does not change the benchmark verdict, and does not estimate scanner accuracy.
It re-verifies the [published historical SAST sidecars](../experiments/sast_historical_20261028.tar.gz)
against the 40 sealed main logs and native receipts, then checks whether the
Bandit report and implemented-test result refer to the same final source bytes.
The [program](sast_provenance_missingness.py), [derived JSON](sast_provenance_missingness_20261030.json),
and [per-final CSV](sast_provenance_missingness_20261030.csv) retain all 40
final candidates in the denominator.

| Final implemented test | Candidates | Source-identical Bandit/test comparison | Evaluator source SHA missing | Evaluator SHA differs from logged source |
| --- | ---: | ---: | ---: | ---: |
| Pass | 25 | 24 | 0 | 1 |
| Fail | 15 | **0** | **15** | 0 |

The comparison is available for **24/25** raw-test passes and **0/15**
raw-test failures. This is outcome-associated source-hash missingness in this local
cohort: every failed final lacks an evaluator source hash. The one passing
final excluded from the comparison is slot 22, whose logged source differs
from the evaluator source hash after redaction. These are descriptive counts,
not a population estimate or a causal effect.

Bandit returned `NO_FINDINGS` for 13 of the 15 failing finals' *logged*
sources, but none of those 13 can be joined to the evaluator's executed source
under the strict hash rule. A finite test failure can also be a functional
failure rather than a security flaw. Therefore the existing 24-case table,
which contains only raw-test passes, cannot measure Bandit's ability to flag
failed candidates, sensitivity, specificity, or general checker agreement.

By task family, the verified final counts are:

| Family | Finals | Raw-test passes | Source-identical comparisons | Missing evaluator SHA |
| --- | ---: | ---: | ---: | ---: |
| Key derivation | 8 | 4 | 3 | 4 |
| Nonce | 8 | 8 | 8 | 0 |
| SQL injection | 8 | 1 | 1 | 7 |
| Weak randomness | 8 | 8 | 8 | 0 |
| XSS | 8 | 4 | 4 | 4 |

The analysis verifies the archive SHA-256 before safe temporary extraction,
then calls the original sidecar verifier, which rechecks log bytes, receipts,
source hashes, scanner reports, and archive inventory. The saved JSON records
the SAST archive, SAST manifest, and sealed-log manifest digests. It does not
run Bandit or execute agent code. From the repository root:

```sh
python3 -B -m analysis.sast_provenance_missingness --check
python3 -B -m unittest tests.test_sast_provenance_missingness -q
```

This finding strengthens the logging requirement for the proposed study:
preserve the evaluator's executed-source hash and raw check outcome at **every
action**, including failures, before attempting a meaningful SAST/checker
agreement analysis. The proposed main-study release gate remains `NOT_READY`.
