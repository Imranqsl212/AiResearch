# The first submitted candidate often stayed the same after opposite feedback

**Excluded post hoc audit, 4 November 2026.** In the older 14-pair C5
continuation pilot, a false `FAIL` changed the agent's *first tool choice*
in many pairs. We joined the source-bound action and candidate audits to ask
whether it also changed the **first submitted bounded-policy candidate**.
These candidates are categorical JSON modes, not patches to production code.

| Older selected C5 cohort | Count |
| --- | ---: |
| Matched pairs | 14 |
| Both arms submitted at least one candidate | 11 |
| Same first candidate SHA-256 among those 11 | **9/11** |
| False arm first chose `INSPECT`, among those 11 | 9/11 |
| Same first candidate after that false-arm `INSPECT` | **8/9** |
| Same complete sequence of submitted candidates | **1/11** |
| Only false arm submitted, truthful arm stopped immediately | 3/14 |

Of the nine exact first-candidate matches, five matched candidates passed the
bounded oracle and four failed it. All nine passed the **weak raw test**.
The five bounded-secure candidates were accepted after truthful `PASS` and
rejected by the persistent hidden veto after false `FAIL`, as that intervention
requires. Thus the early action divergence did not usually imply a different
first submitted candidate in this selected cohort. The later sequences often
diverged, and this analysis does not establish that the initial feedback was
behaviorally irrelevant. Inspecting can still affect later choices.

## Separate checks in later one-shot cohorts

| Cohort | Completed pairs | Both arms submitted | Same first candidate among both | Same full candidate sequence among both |
| --- | ---: | ---: | ---: | ---: |
| First temperature-zero wave | 3 | 3 | 2/3 | 2/3 |
| Second temperature-zero wave | 2 | 2 | 2/2 | 2/2 |
| First temperature-0.3 wave, technically stopped | 4 | 4 | 1/4 | 1/4 |
| Second temperature-0.3 wave, technically stopped | 4 | 2 | 0/2 | 0/2 |

In the last wave, the other two pairs had a submission only after false
`FAIL`, so they are excluded from its "among both" denominator. These four
cohorts use different tasks, schedules, feedback persistence, and temperatures;
the waves were planned sequentially and the temperature-0.3 waves stopped
early. The table is **not** a pooled comparison or an estimate of a temperature
effect. It challenges a broad claim that first-candidate parity must follow
from feedback identity in every setting.

The [read-only program](c5_first_submission_parity_20261104.py) reruns the
archived source-bound audits, compares each older action log's SHA-256 with its
receipt, joins every `ATTEMPT` event to its candidate receipt hash, and then
counts first and full sequences. The [JSON](c5_first_submission_parity_20261104.json)
retains all 14 old pairs, exact per-arm candidate hashes, and separate later
wave summaries. No model is called and no candidate code is executed.

```sh
python3 -B -m analysis.c5_first_submission_parity_20261104 --check
python3 -B -m unittest -q tests.test_c5_first_submission_parity_20261104
```

The older sample was selected after secure onsets, its first pair preceded
the remaining schedule, and the false arm had a **persistent veto** after the
initial verdict. The tasks lack independent human semantic admission. These
counts support a narrow observation about visible candidate identities in
saved local trajectories; they do not establish a population feedback effect,
causal mechanism, or real-world security outcome.
