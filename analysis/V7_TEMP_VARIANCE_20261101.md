# Excluded v7 temperature 0.3 wave: prescheduled partial run

**Status:** `WAVE_STOPPED`, 1 November 2026. The [32-slot plan](../docs/EXCLUDED_V7_TEMP_VARIANCE_20261101_PLAN.md) and producing code were committed and pushed before the first model request. This is an excluded engineering pilot: none of these episodes is eligible for the main study. The [machine-readable recount](v7_temp_variance_20261101.json) validates the archived schedule, append-only event journal, source commit, model requests, finite evaluations, and C5 branches. The [repository archive](../experiments/runs/v7_temp03_four_seed_20261101) contains 654 files; its path-and-content tree SHA-256 is `a6a7e604cc3f7ff394d345f73124d741a4c174c6a8934ae90713928d708bed00`. It was copied byte-for-byte from the write-once original under `/private/tmp`, then eight occurrences of the local user workspace prefix were removed from **one technical stderr log** before publication. All other 653 files are unchanged. The [redaction manifest](v7_temp_variance_20261101_public_redaction.json) records the original tree SHA-256 `f0fdaaafd95109b3fe44e3f86357a0dff91b3de11a6324bc059eb9b37d3d430c`, both file hashes, and the published tree hash. The scientific requests, responses, decisions and receipts were not redacted.

## Scheduled-slot accounting

The wave prescribed eight task families with four precursor seeds each at `temperature=0.3`. Seven precursors were source-bound verified: four in `csrf_origin` and three in `deserialization_allowlist`. All four CSRF precursors reached an independently verified first finite-secure submission, yielding four source-bound verified truthful-`PASS`/false-`FAIL` pairs. The three completed deserialization precursors had no secure onset, so no pair was opened. The fourth deserialization precursor was invalidated after four archived decisions because the local Ollama `/api/tags` identity check exceeded its 10-second transport timeout. The dispatcher stopped immediately. The remaining **24 prescheduled precursors were not run**. There was no retry, replacement, or result-dependent reselection.

| Family | Verified precursors / scheduled | Verified secure onsets | Verified pairs | No onset | Technical invalidation | Unstarted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `csrf_origin` | 4/4 | 4 | 4 | 0 | 0 | 0 |
| `deserialization_allowlist` | 3/4 | 0 | 0 | 3 | 1 | 0 |
| Other six families | 0/24 | 0 | 0 | 0 | 0 | 24 |
| **All scheduled slots** | **7/32** | **4** | **4** | **3** | **1** | **24** |

## Paired outcomes and visible trajectories

The terminal finite reference found regression in **0/4 truthful-`PASS`** continuations and **3/4 false-`FAIL`** continuations. All three discordant pairs are CSRF repeats; the fourth pair retained the finite-secure terminal candidate in both arms. In the three discordant pairs, the false-`FAIL` arm visibly tried `origin_only` and then ended at `reject_all`, whereas the truthful arm ended at `token_and_origin`. This is a change in the task's categorical finite policy, not a verified production-code security strategy. Two discordant seeds had identical action/candidate signatures in both arms, and all three false-`FAIL` arms had the same signature. Their count is therefore not three distinct behavioral mechanisms or three independent task-family replications.

Across the seven verified precursors there were 14 submissions, including six with raw `PASS` but finite-oracle `INSECURE`; none of those six passed the stronger check. The truthful branches had one raw-`PASS`/oracle-`INSECURE` submission and the false branches had four; none passed the stronger check. These are per-submission findings, not terminal episode rates. The archived requests show `temperature=0.3` and the planned seed; there were six distinct precursor action/candidate signatures among the seven verified precursors. No confidence interval, p-value, or population effect is estimated from this selected, technically truncated batch.

## Technical cause and inference limit

The failed slot has an archived `LiveDispatchError` with invalidation reason `MODEL_IDENTITY_UNAVAILABLE`; the runner's stderr attributes it to an Ollama `/api/tags` timeout. A later read-only request to `/api/tags` took about 7.8 seconds, close to the 10-second identity limit. This supports a timeout explanation but does not reconstruct the unobserved fifth decision or prove why the server slowed. The failed precursor and 24 unstarted slots are retained in the denominator. A [separately planned post-failure wave](V7_TEMP_VARIANCE_SECONDWAVE_20261101.md) used a longer identity timeout under a new schedule and archive identifier; it also stopped technically, and its outcomes are not pooled here.

The [reproducible public-archive scanner](scan_public_excluded_archive.py) found zero hits in 14 sensitive-pattern categories across all 654 published files. It reported 13 uses of the fixed `/private/tmp` output root as execution metadata. This pattern scan cannot establish general privacy clearance or detect unfamiliar/encoded secrets; the original local archive and the published redaction should still be inspected by a human before journal deposit.

The eight authored v7 task families have not passed human semantic admission. Repeated seeds on one fixed CSRF task do not establish a general effect across security repairs. `SECURE` here means bounded agreement with the finite reference, not real-world safety. The early pilot waves at temperature 0 were observed before this plan and cannot be pooled as if they formed a single prospective sample.

## Read-only reproduction

From the repository root:

```sh
python3 -B -m analysis.v7_temp_variance_20261101 --check
python3 -B -m unittest -q tests.test_v7_temp_variance_20261101
python3 -B -m analysis.scan_public_excluded_archive \
  experiments/runs/v7_temp03_four_seed_20261101 \
  --planned-temp-root /private/tmp/research-v7-temp03-four-seed-20261101
```

The analysis code was committed while the fixed wave was running, before its author inspected the wave outputs. Its outcome definitions were already specified in the pushed plan. The archive includes the fixed preflight source commit `d125c34f337ec47c375f7f7aeaf6a2295f3de2ac` and the plan SHA-256 `62487055f2724fc987785d6db17a4dde726cca64cf5f895d033255fb8ebdba00`. No Git commit or hash alone is an independent timestamp or external chain of custody.
