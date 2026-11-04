# A transient provider-latency burst in an excluded v7 wave

**Exploratory runtime audit, 4 November 2026.** The five selected v7 archives
with complete native Ollama response metrics contain **208 completed**
`qwen3:4b` responses. The [read-only recount](v7_boundary_provider_latency_20261104.py)
first verifies each archive through its existing source-bound analyzer, then
matches every response byte string to its saved dispatch-return SHA-256.
The [machine-readable report](v7_boundary_provider_latency_20261104.json)
keeps the five sequentially conducted cohorts separate.

| Excluded cohort | UTC window of completed response timestamps | Completed responses | Median total seconds | Max total seconds | Total >30 s | Unattributed >30 s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Temperature-zero second wave | Nov 1, 07:27–07:28 | 20 | 2.33 | 11.68 | 0 | 0 |
| First stopped temperature-0.3 wave | Nov 1, 07:51–07:55 | 55 | 2.98 | 22.19 | 0 | 0 |
| **Second stopped temperature-0.3 wave** | **Nov 1, 08:04–08:31** | **50** | **8.65** | **155.81** | **13** | **8** |
| Cross-family seed-301 wave | Nov 4, 14:42–14:43 | 28 | 2.31 | 11.63 | 0 | 0 |
| Six-slot seeds-302–304 wave | Nov 4, 15:00–15:02 | 55 | 2.31 | 14.52 | 0 | 0 |

The second stopped wave's archived preflight and the first stopped wave's
preflight both bind the same `qwen3:4b` digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`
and Ollama server version `0.35.0`. The archive does **not** measure host load,
memory pressure, concurrent processes, or network/queue conditions. It cannot
prove that these operating conditions were the same. The two waves also ran
sequentially with different schedules; their counts are descriptions of
archived requests, not independent model-trial rates.

## Why output length alone does not account for the burst

Ollama reports `total_duration`, `load_duration`, `prompt_eval_duration`, and
`eval_duration` in nanoseconds. We call their arithmetic difference
**unattributed duration**; it is a bookkeeping residual, not a diagnosis of
queueing or hardware failure. The second stopped wave has 8/50 responses with
more than 30 seconds of this residual (maximum **122.95 s**), while the other
four selected cohorts have 0/158. At more than 60 seconds, the counts are
3/50 versus 0/158. These thresholds were explored *after* seeing the records;
no p-value, confidence interval, or multiple-testing claim is made.

A matched continuation illustrates the measurement issue. In CSRF seed 204,
the first false-`FAIL` response reports **142.60 s** total for 1,239 prompt
tokens and 32 output tokens; **122.95 s** is outside its three named phases.
The first truthful-`PASS` response reports **6.99 s** for 1,240 prompt tokens
and 33 output tokens. These responses occurred sequentially, so the contrast
cannot be attributed to the feedback. It shows that elapsed time or timeouts
in this wave cannot be interpreted as a pure measure of agent deliberation.

## Scope and limitation

Only completed provider responses are counted. The second stopped wave also
has a generation request that timed out at its fixed 180-second limit; no
provider response exists for it, and 22 planned precursors were never started.
The first stopped wave had a separate identity-check timeout, also outside the
completed response denominator. The five archives were chosen because they
preserve native response durations; older C5 pilot logs do not. The 30-second
threshold and the seed-204 example are exploratory choices among several
examined metrics, so this is a technical sensitivity finding, not an estimate
of a feedback effect or model reliability in general. The research tasks still
lack independent human semantic admission.

Reproduce from the repository root:

```sh
python3 -B -m analysis.v7_boundary_provider_latency_20261104 --check
python3 -B -m unittest -q tests.test_v7_boundary_provider_latency_20261104
```
