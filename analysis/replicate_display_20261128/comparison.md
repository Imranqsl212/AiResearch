# Does the display change choices beyond ordinary repeat variation?

Each of sixteen archived CPython histories received two fresh draws with no new output and two draws with the same nonrevealing execution display. All four assignments retained the same model, menu and history.

| Endpoint | Complete / assigned histories | Cross-arm disagreement | Within-arm disagreement | Cross minus within | Bounds across all assigned histories |
| --- | ---: | ---: | ---: | ---: | --- |
| source | 14 / 16 | 0.30357 | 0.28571 | 0.01786 | [-0.01562, 0.07812] |
| function | 14 / 16 | 0.10714 | 0.14286 | -0.03571 | [-0.03125, -0.03125] |

Cross and within averages shown in the table use the same complete histories. Each history contributes four cross-arm comparisons and two within-arm comparisons. A history receives equal weight in the final estimate. The scheduled bounds allow every missing response to select any offered source and use the exact attainable extremes within each history, separately for each endpoint.

## Repair and preservation

| Display | Repaired / scored / assigned | Preserved / scored / assigned |
| --- | ---: | ---: |
| none | 4 / 8 / 8 | 24 / 24 / 24 |
| shared | 5 / 7 / 8 | 23 / 23 / 24 |

There are two planned native replies per history and display. The four defective histories repeat one Luna edit; the twelve working histories cover the other starting implementation choices.

Missing calls: INVALID_RESPONSE=2.

## Every history

| Archived history | Start | None 1 / 2 | Shared 1 / 2 | Difference in source disagreement | Difference in functional disagreement |
| --- | --- | --- | --- | ---: | ---: |
| gpt-6-luna_cpython_correct_r1_early | p3 | p7 / p7 | p5 / — | — | — |
| gpt-6-luna_cpython_correct_r1_late | p3 | p3 / p3 | p3 / p5 | 0 | 0 |
| gpt-6-luna_cpython_correct_r2_early | p3 | p5 / p3 | p5 / p5 | 0 | 0 |
| gpt-6-luna_cpython_correct_r2_late | p3 | p3 / p7 | p3 / p5 | -0.25 | -0.5 |
| gpt-6-luna_cpython_defective_r1_early | p5 | p7 / p7 | p7 / p7 | 0 | 0 |
| gpt-6-luna_cpython_defective_r1_late | p5 | p7 / p7 | p7 / p7 | 0 | 0 |
| gpt-6-luna_cpython_defective_r2_early | p7 | p7 / p7 | p7 / p7 | 0 | 0 |
| gpt-6-luna_cpython_defective_r2_late | p7 | p5 / p7 | — / p7 | — | — |
| gpt-6.2-astra_cpython_correct_r1_early | p5 | p5 / p5 | p5 / p5 | 0 | 0 |
| gpt-6.2-astra_cpython_correct_r1_late | p5 | p5 / p5 | p5 / p5 | 0 | 0 |
| gpt-6.2-astra_cpython_correct_r2_early | p5 | p5 / p5 | p5 / p5 | 0 | 0 |
| gpt-6.2-astra_cpython_correct_r2_late | p5 | p5 / p5 | p5 / p5 | 0 | 0 |
| gpt-6.2-astra_cpython_defective_r1_early | p7 | p7 / p5 | p7 / p7 | 0 | 0 |
| gpt-6.2-astra_cpython_defective_r1_late | p7 | p5 / p5 | p7 / p7 | 1 | 0 |
| gpt-6.2-astra_cpython_defective_r2_early | p7 | p7 / p5 | p5 / p7 | -0.5 | 0 |
| gpt-6.2-astra_cpython_defective_r2_late | p7 | p5 / p7 | p7 / p7 | 0 | 0 |

If the two fresh calls in each condition are independent draws from stationary categorical distributions p and q and independent across conditions, the expected difference for the source equals half the sum of squared probability differences. For binary held-out correctness it equals the squared difference in pass probabilities. An individual sample estimate can be negative. Multiple pair comparisons reuse responses, so treating the six comparisons as independent observations would overstate precision. This measurement cannot establish an effect across tasks or equivalence of the distributions.

Offline recount: `python3 -I analysis/replicate_display_report.py analysis/replicate_display_20261128 --check`.
