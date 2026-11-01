# When a raw check passed but the bounded property failed

This is a **post hoc, excluded** candidate-level recount of the older 14-pair C5 engineering pilot. It is not a new model run, a main-study result, or a general security estimate. Its persistent false-`FAIL` rule and common three-decision continuation notice differ from the [newer one-shot pilot](FRESH_MATCHED_VERDICT_PILOT_20261101.md); the cohorts are not pooled.

## Recount method

The [read-only script](c5_candidate_discordance_20261101.py) first requires the existing [14-pair archive audit and regression recount](C5_PAIRED_REGRESSION_RECOUNT_20261101.md) to match their tracked result. It then reopens every archived post-onset `ATTEMPT`, recomputes the candidate with the source-bound C1 and C5 finite evaluator and separate reference, and requires the recomputed candidate hash, raw check, bounded-oracle result, and benchmark verdict to match the saved event. There were **45** verified submissions: 28 after truthful `PASS` and 17 after false `FAIL`. Every counted submission comes from one of the 14 verified pairs.

`Raw PASS / oracle INSECURE` means the implemented raw check accepted a candidate that failed the **authored bounded finite property**, as checked by the evaluator and a separate reference implementation. It does **not** mean the benchmark's final verdict accepted that candidate, and it does not prove real-world exploitability. `Raw PASS / oracle SECURE / verdict FAIL` is a different event: the finite property passed, but the C5 veto still rejected the candidate.

## Candidate-level outcomes

| Raw check | Bounded oracle SECURE | Bounded oracle INSECURE | Total |
| --- | ---: | ---: | ---: |
| PASS | 23 | **21** | 44 |
| FAIL | 0 | 1 | 1 |
| Total | 23 | 22 | **45** |

The 21 raw-`PASS`/oracle-`INSECURE` submissions occurred in **11 of 14 pair slots** and **8 of 10 families**. They represent **9 distinct candidate SHA-256 values globally**, or **12 distinct family–candidate combinations**. Across all 45 submissions there were 19 distinct hashes and 23 family–hash combinations. Thus 21/45 is a submission count in this selected archive, **not 21 independent tests or a population error rate**.

| Delivered initial verdict arm | Submissions | Raw PASS / oracle INSECURE | Raw PASS / oracle SECURE | Raw FAIL / oracle INSECURE | Oracle SECURE but benchmark FAIL |
| --- | ---: | ---: | ---: | ---: | ---: |
| Truthful PASS | 28 | 13 | 14 | 1 | 0 |
| False FAIL | 17 | 8 | 9 | 0 | 9 |

The two mismatches must be kept separate: 21 submissions exposed a weak raw-check signal relative to the bounded oracle; 9 other submissions satisfied that oracle but were rejected under the false-verdict arm's persistent veto. The [terminal regression recount](C5_PAIRED_REGRESSION_RECOUNT_20261101.md) found 5/14 truthful-PASS and 7/14 false-FAIL branches ending with an oracle-insecure candidate. That mixed pair result does not isolate a general effect of the false verdict.

### Family coverage

| Family | Pairs | Submissions | Raw PASS / oracle INSECURE | Distinct discordant hashes | Affected pair slots |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ambiguous_parameters` | 1 | 4 | 1 | 1 | 1 |
| `authorization` | 1 | 1 | 0 | 0 | 0 |
| `counter_race` | 2 | 9 | 2 | 1 | 1 |
| `deserialization_allowlist` | 2 | 6 | 6 | 2 | 2 |
| `dns_rebinding` | 1 | 4 | 3 | 2 | 1 |
| `environment_injection` | 2 | 4 | 4 | 2 | 2 |
| `kdf_salt` | 1 | 4 | 1 | 1 | 1 |
| `nonce_uniqueness` | 2 | 8 | 3 | 2 | 2 |
| `path-boundary` | 1 | 1 | 0 | 0 | 0 |
| `signature_algorithm` | 1 | 4 | 1 | 1 | 1 |

The archive selected secure agent-generated onsets from an earlier 40-slot feasibility block, and the first pair was selected before the remaining 13 were scheduled. Both arms received an extra continuation notice; the older false arm repeated its veto after later secure submissions. Multiple submissions and repeated candidate hashes share the same tasks, model, and context. These dependencies preclude treating the table as independent trials, computing a population interval, or pooling it with the one-shot pilot. The bounded oracle itself still needs human semantic review before main-study use.

## Reproduce

From the repository root:

```sh
python3 -B -m analysis.c5_candidate_discordance_20261101 --check
python3 -B -m unittest -q tests.test_c5_candidate_discordance_20261101
```

The [machine-readable result](c5_candidate_discordance_20261101.json) lists every counted submission with its slot, family, arm, candidate SHA-256, raw result, bounded-oracle result, and benchmark verdict. The check fails if archived evidence or the tracked result changes.
