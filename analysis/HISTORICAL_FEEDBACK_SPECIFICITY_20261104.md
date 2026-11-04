# Historical “diagnostic” feedback was fixed by task family

**Excluded, retrospective audit — 4 November 2026.** The [read-only audit](historical_feedback_specificity_20261104.py)
opens the sealed 40-run main archive, checks every log against the historical
receipt inventory, and inspects the evaluator source at commit
`98a4dcf414672c1725e4acdb9f08045370aa7f64`. The
[machine-readable report](historical_feedback_specificity_20261104.json)
contains only hashes and aggregate counts, no candidate source.

The evaluator's “diagnostic” condition selected one prewritten string per
family whenever the **public** check failed. It did not select a message
from a candidate-specific failing test. Among the 77 logged submissions, the
`attempt` tool produced 30 diagnostic-condition FAIL observations, using
exactly **one failure message per family**. The weak-feedback condition
produced 31 failed `attempt` observations, all with the same generic message.

| Family | Diagnostic FAIL observations | Distinct diagnostic messages | U/diagnostic terminal candidates with raw tests PASS and public FAIL |
| --- | ---: | ---: | ---: |
| Key derivation | 8 | 1 | 1 |
| Nonce | 4 | 1 | 2 |
| SQL injection | 8 | 1 | 0 |
| Weak randomness | 4 | 1 | 2 |
| XSS | 6 | 1 | 0 |
| **Total** | **30** | **5 family strings** | **5 of 10 U/diagnostic episodes** |

In **11 diagnostic runs**, two or more failed submissions had different
evaluator-receipt source hashes but received the exact same family message.
More directly, five U/diagnostic **final** candidates passed their implemented
family tests while the public feedback said FAIL using that fixed diagnostic
wording. For slots 10, 15, 24, 32, and 35, the final evaluator's executed
source SHA-256, final candidate receipt SHA-256, and logged last submission
SHA-256 agree. Their public last-step feedback and archived terminal receipt
therefore refer to the same bytes. The hidden policy veto explains the public
FAIL. The exact five source and receipt hashes are in the JSON report.

This result narrows what the feedback factor measures: `D` supplies a static
family-level cue, while `W` supplies a static generic cue. A diagnostic
message mentioning a flaw is **not evidence** that the named flaw was detected
in the current candidate. Passing finite tests is also not proof that the
candidate is secure. The records do not preserve raw test results for each
intermediate action; this source-joined raw-PASS claim applies only to the
five terminal candidates. Eleven other logged submissions have a
logger-redaction source-hash mismatch and cannot support a source-specific
claim. No causal claim about the model's response to wording follows from
this retrospective audit.

Reproduce from the repository root:

```sh
python3 -B -m analysis.historical_feedback_specificity_20261104 --check
python3 -B -m unittest -q tests.test_historical_feedback_specificity_20261104
```
