# Showing an execution before a single edit on two Python tasks

The seven original implementations comprise four faulty and three working sources on two tasks. Both model configurations saw each source in all three conditions. The fourteen model/source blocks therefore contribute eight faulty and six working starts per condition. Each assigned call had a single decision from a finite menu. Each project used its original six held-out checks.

## Inputs and outputs

- cpython received `{3: 'amber', 7: 'cobalt'}` in the shared-output condition and `{20: 'cobalt', 3: 'amber'}` in the revealing condition.
- dateutil received `2025-02-16T11:34:52+03:20` in the shared-output condition and `2025-02-16T11:34:52-03:20` in the revealing condition.

Every implementation in each project gave the reference answer on the shared input. On the revealing input, each of the four faulty sources differed from its reference, and each of the three working sources agreed.

## Repair and preservation

A new implementation that still passes counts as preservation. Fractions use scored responses within the corresponding starting stratum. Scored/scheduled reports overall response coverage.

| Project | Model | Display | Scored/scheduled | Defects repaired | Working states preserved | Working states damaged | Rewritten and still working |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Both | Both | No new output | 14/14 | 8/8 | 6/6 | 0/6 | 2/6 |
| Both | Both | Shared | 14/14 | 8/8 | 5/6 | 1/6 | 2/6 |
| Both | Both | Revealing | 14/14 | 8/8 | 6/6 | 0/6 | 2/6 |
| cpython | gpt-6-luna | No new output | 4/4 | 2/2 | 2/2 | 0/2 | 1/2 |
| cpython | gpt-6-luna | Shared | 4/4 | 2/2 | 2/2 | 0/2 | 1/2 |
| cpython | gpt-6-luna | Revealing | 4/4 | 2/2 | 2/2 | 0/2 | 1/2 |
| cpython | gpt-6.2-astra | No new output | 4/4 | 2/2 | 2/2 | 0/2 | 1/2 |
| cpython | gpt-6.2-astra | Shared | 4/4 | 2/2 | 2/2 | 0/2 | 1/2 |
| cpython | gpt-6.2-astra | Revealing | 4/4 | 2/2 | 2/2 | 0/2 | 1/2 |
| dateutil | gpt-6-luna | No new output | 3/3 | 2/2 | 1/1 | 0/1 | 0/1 |
| dateutil | gpt-6-luna | Shared | 3/3 | 2/2 | 0/1 | 1/1 | 0/1 |
| dateutil | gpt-6-luna | Revealing | 3/3 | 2/2 | 1/1 | 0/1 | 0/1 |
| dateutil | gpt-6.2-astra | No new output | 3/3 | 2/2 | 1/1 | 0/1 | 0/1 |
| dateutil | gpt-6.2-astra | Shared | 3/3 | 2/2 | 1/1 | 0/1 | 0/1 |
| dateutil | gpt-6.2-astra | Revealing | 3/3 | 2/2 | 1/1 | 0/1 | 0/1 |

Missing outcomes: none.

## Matched contrasts

The planned primary contrast compares revealing with no display in faulty-start blocks. Both calls in each pair began with the same model and source. Only complete pairs are scored. Different implementations can yield the same held-out result.

| First vs second display | Start | Complete/scheduled | Both pass | Second alone passes | First alone passes | Neither passes | Different final source |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No new output vs Revealing | Faulty | 8/8 | 8 | 0 | 0 | 0 | 0/8 |
| No new output vs Revealing | Working | 6/6 | 6 | 0 | 0 | 0 | 0/6 |
| No new output vs Shared | Faulty | 8/8 | 8 | 0 | 0 | 0 | 0/8 |
| No new output vs Shared | Working | 6/6 | 5 | 0 | 1 | 0 | 1/6 |
| Shared vs Revealing | Faulty | 8/8 | 8 | 0 | 0 | 0 | 0/8 |
| Shared vs Revealing | Working | 6/6 | 5 | 1 | 0 | 0 | 1/6 |

## Outcomes for every model and starting source

A source ID belongs to its project. Reading across a row shows the actual implementations behind both concordant and discordant grades.

| Project | Model | Starting source | No new output | Shared output | Revealing output |
| --- | --- | --- | --- | --- | --- |
| cpython | gpt-6-luna | p2 (fail) | p7 (pass) | p7 (pass) | p7 (pass) |
| cpython | gpt-6-luna | p3 (fail) | p7 (pass) | p7 (pass) | p7 (pass) |
| cpython | gpt-6-luna | p5 (pass) | p7 (pass) | p7 (pass) | p7 (pass) |
| cpython | gpt-6-luna | p7 (pass) | p7 (pass) | p7 (pass) | p7 (pass) |
| cpython | gpt-6.2-astra | p2 (fail) | p7 (pass) | p7 (pass) | p7 (pass) |
| cpython | gpt-6.2-astra | p3 (fail) | p7 (pass) | p7 (pass) | p7 (pass) |
| cpython | gpt-6.2-astra | p5 (pass) | p7 (pass) | p7 (pass) | p7 (pass) |
| cpython | gpt-6.2-astra | p7 (pass) | p7 (pass) | p7 (pass) | p7 (pass) |
| dateutil | gpt-6-luna | k3 (pass) | k3 (pass) | p7 (fail) | k3 (pass) |
| dateutil | gpt-6-luna | p7 (fail) | k3 (pass) | k3 (pass) | k3 (pass) |
| dateutil | gpt-6-luna | t9 (fail) | k3 (pass) | k3 (pass) | k3 (pass) |
| dateutil | gpt-6.2-astra | k3 (pass) | k3 (pass) | k3 (pass) | k3 (pass) |
| dateutil | gpt-6.2-astra | p7 (fail) | k3 (pass) | k3 (pass) | k3 (pass) |
| dateutil | gpt-6.2-astra | t9 (fail) | k3 (pass) | k3 (pass) | k3 (pass) |

These are exploratory, one-call choices per model, source and condition. The seven implementations belong to two previously selected tasks. The two configurations and repeated displays do not supply additional projects or establish differences between model populations.

From the repository root run `python3 -B -m analysis.cross_project_display_report --check`.

[Assignment](plan.json) · [Functional calibration](calibration.json) · [Decision ledger](results.json)
