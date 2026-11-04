# Identical code, different public checker answers: a historical source match

**Exploratory source-bound audit, 4 November 2026.** The 40 historical episodes contain 77 code submissions. Their saved call/observation pairs support a narrower finding than a raw test replay: **six distinct family–source groups** have identical candidate bytes that received public PASS in a repairable (`R`) episode and public FAIL in a policy-rejected (`U`) episode. This covers **ten U first submissions** across four families. The logged source SHA-256 equals the per-action verifier source SHA-256 in all matched observations; records with mismatched hashes are excluded.

| Family | Exact source SHA-256 prefix | R PASS slots | U FAIL first-submission slots |
| --- | --- | --- | --- |
| `key-derivation` | `a1dcc0f2f359` | 000001 | 000024 |
| `nonce` | `747dd6f9d1ee` | 000011, 000029, 000030 | 000009, 000031 |
| `weak-randomness` | `16fd5cf59a2a` | 000033 | 000034 |
| `weak-randomness` | `9964d026480a` | 000014, 000016, 000036 | 000013, 000015, 000035 |
| `xss` | `06e5580ea602` | 000025 | 000020 |
| `xss` | `a2cd92f5cd56` | 000017, 000019, 000028 | 000026, 000027 |

## The XSS case hidden by final-only counting

Three `U` XSS runs (slots 20, 26, 27) first submitted a dictionary-returning `html.escape` implementation with **exactly the same source bytes** as at least one `R` submission that got public PASS. Their first public replies were FAIL. The saved subsequent submissions in all three changed the `handle` function's return shape from a dictionary to a non-dictionary expression. The final raw finite test failed in all three. The fixed XSS evaluator indexes `r['html']`; the changed return shape no longer satisfies that interface. XSS had **0/4 terminal U test–gate disagreements**, so a terminal-only audit misses these observed first-step public-response divergences.

| U XSS slot | First-source SHA prefix | Later return shapes | Final raw test |
| --- | --- | --- | --- |
| 000020 | `06e5580ea602` | non_dictionary → non_dictionary | FAIL |
| 000026 | `a2cd92f5cd56` | non_dictionary | FAIL |
| 000027 | `a2cd92f5cd56` | non_dictionary → non_dictionary | FAIL |

The original archived logs are under [`experiments/raw_archive/rag-overnight-v2-main-0-5-0/runs/`](../experiments/raw_archive/rag-overnight-v2-main-0-5-0/runs/). For each attempt, this analysis pairs `TOOL_CALL` and `TOOL_OBSERVATION` by exact run/step/tool, hashes `parameters.source`, and requires equality with `verifier_result.source_sha256`. The historical candidate bridge sends only domain, family, and source into the fixed container test; it applies the R/U acceptance condition after the test. The XSS test and bridge are read from the recorded study source commit. The [JSON report](historical_matched_source_feedback_20261104.json) records every group, slot, step, and source hash. The audit revalidates the sealed historical archive through the existing paper pipeline and checks that the original and working log hashes agree.

**Limit.** The historical per-action receipts do not retain the U arm's raw family-test result. A cross-run match therefore establishes **public PASS/FAIL divergence for the same recorded source**, not a directly archived U raw PASS. The episodes differ in their histories; the later XSS revision sequence is observable but its cause is not identified. Passing the narrow XSS test would not prove general XSS safety. This is a post hoc hypothesis for a prospective source-matched feedback experiment, not a population effect estimate.

## Reproduce

```sh
python3 -B -m analysis.historical_matched_source_feedback_20261104 --check
python3 -B -m unittest -q tests.test_historical_matched_source_feedback_20261104
```
