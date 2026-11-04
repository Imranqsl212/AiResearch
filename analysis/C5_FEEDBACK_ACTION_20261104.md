# A false-failure inspection loop in one excluded C5 pilot

The [source-bound action recount](c5_feedback_action_20261104.json) opens all 14
matched pairs in the **older** C5 engineering archive. This cohort was selected
after 14 agent-generated secure onsets in ten authored task families. Its first
pair was observed before the other 13 were scheduled. Both arms had the same
model seed, tool schema, prior history, and extra three-decision continuation
notice. The initial public observations differed only in verdict and feedback;
the false arm also kept a **persistent veto** after later secure submissions.
These tasks lack independent human semantic admission.

## What the agent actually did

| Archived action outcome | Truthful `PASS` | False `FAIL` |
| --- | ---: | ---: |
| First post-onset decision was `INSPECT` | **0/14 pairs** | **12/14 pairs** |
| Any `INSPECT` after onset | 0/14 | 13/14 |
| Total `INSPECT` decisions | 0 | **24** |
| Total new candidate submissions (`ATTEMPT`) | **28** | **17** |
| Used all three decisions | 11/14 | 14/14 |
| Ended because the decision budget ran out | 6/14 | **13/14** |

In 11 of 14 false-feedback arms, the exact action pattern was
`INSPECT → ATTEMPT → INSPECT`. At least one false arm inspected in **each of
the ten selected families**. The truthful arm never inspected. Because the
first decision occurs before any later C5 veto, the 12-versus-0 first-action
contrast is the cleanest observation about the *initial* feedback difference
in this archive. Later action counts also reflect the persistent veto.

`INSPECT` is an agent-requested tool action that returns the current candidate;
it is not a submitted repair. A count of code submissions alone would miss the
longer false-feedback trajectories: they made **fewer** code submissions while
using **more** decisions and usually exhausting the budget. The records do not
show private reasoning or establish that any inspection was useless.

The previous [terminal regression recount](C5_PAIRED_REGRESSION_RECOUNT_20261101.md)
found 5/14 bounded regressions after truthful `PASS` and 7/14 after false
`FAIL`. That small, mixed terminal contrast is a distinct endpoint. The new
finding concerns *visible tool choice* after feedback, not proof of worse
security or rational stopping.

## Attempt to disprove a general feedback pattern

The analysis separately replays four later **one-shot** cohorts and checks
their saved source-bound reports. They use different schedules and task sets;
their counts are never pooled with the older pilot.

| Later cohort | Completed pairs | First `INSPECT` after truthful `PASS` | First `INSPECT` after false `FAIL` |
| --- | ---: | ---: | ---: |
| First temperature-zero wave | 3 | 0 | 0 |
| Second temperature-zero wave | 2 | 0 | 0 |
| First temperature-0.3 wave, stopped early | 4 | 1 | 1 |
| Second temperature-0.3 wave, stopped early | 4 | 0 | 0 |

The strong inspection asymmetry did **not** recur in these later records.
Their false verdict lasted one initial observation rather than persisting,
and the temperature-0.3 waves were technically truncated. This comparison
cannot identify which protocol, task, prompt, or runtime difference accounts
for the change. It does falsify a simple description that false feedback
*always* produces an inspection loop in this model.

## Inference boundary and next test

This is a post hoc selected engineering cohort, with repeated task families,
one local model, and shared prompts. There is no population effect estimate,
p-value, confidence interval, or eligible main-study episode. A future admitted
paired protocol could predeclare **first action after feedback** and **fraction
of decisions spent inspecting** alongside final bounded-property outcome.
It should use the same candidate and history in both arms, record every raw
check, and compare one-shot with persistent feedback as distinct interventions.

Reproduce from the repository root:

```sh
python3 -B -m analysis.c5_feedback_action_20261104 --check
python3 -B -m unittest -q tests.test_c5_feedback_action_20261104
```

The script invokes the existing 14-pair archive integrity and finite-oracle
recount, verifies every action log against its archived SHA-256 receipt, and
rebuilds the four later reports before using their action signatures. It never
calls the agent or executes submitted code.
