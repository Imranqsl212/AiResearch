# Choosing code after an identical value is given a different source

Each task supplies two programs and a single input where their outputs differ. Under each caption a matched block displays each possible output once. Tracking means choosing its producing program on both calls. Under the required caption a tracking block satisfies both disclosed target rules. Under the anonymous or named execution caption it follows both observed values without evidence about which installation convention is required.

| Caption | Both values tracked / complete blocks | Both opposed | Always kept | Always switched | Bounds over assigned blocks |
| --- | ---: | ---: | ---: | ---: | --- |
| anonymous | 8 / 8 | 0 | 0 | 0 | [8, 64] |
| named | 2 / 8 | 0 | 6 | 0 | [2, 58] |
| required | 8 / 8 | 0 | 0 | 0 | [8, 64] |

The following secondary contrast was added after the protocol was frozen and before reserve responses were examined. It subtracts the number of blocks choosing the implementation opposite both displayed values from the number following both values. Constant choices contribute zero. Dividing by the complete-block denominator gives the difference in the fraction choosing A upon displaying A's value versus displaying B's value. Under independent, stationary value-insensitive choices with probability p of selecting A, both-follow and both-oppose each have probability p(1−p), so their expected difference is zero.

| Caption | Aligned minus opposed / complete blocks | Bounds on signed count over all assignments |
| --- | ---: | ---: |
| anonymous | +8 / 8 | [-48, +64] |
| named | +2 / 8 | [-54, +58] |
| required | +8 / 8 | [-48, +64] |

## Matched change in tracking

| First caption | Second caption | Complete / assigned | Only second tracks | Only first tracks | Both track | Neither tracks | Bounds on net gain |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| anonymous | required | 8 / 64 | 0 | 0 | 8 | 0 | [-56, +56] |
| named | required | 8 / 64 | 6 | 0 | 2 | 0 | [-50, +62] |

## Repair, preservation and calls

| Caption | Valid / scheduled calls | Repaired / scored / assigned | Preserved / scored / assigned |
| --- | ---: | ---: | ---: |
| none | 8 / 64 | 0 / 8 / 64 | 8 / 8 / 64 |
| anonymous | 16 / 128 | 8 / 16 / 128 | 8 / 16 / 128 |
| named | 16 / 128 | 2 / 16 / 128 | 14 / 16 / 128 |
| required | 16 / 128 | 8 / 8 / 64 | 8 / 8 / 64 |

56 valid native calls contribute 96 target assessments. Only the required caption identifies the target. Under all other captions the same decision is assessed under both alternatives, so exactly one target assessment passes per valid call. This half-correct rate is imposed by the design. Assigning a value to the current or alternative candidate in the named caption supplies additional information beyond identifying the value as observed.

Missing calls: UNSTARTED=392.

## Tracking by requested configuration

| Model | Task panel | Anonymous | Named | Required |
| --- | ---: | ---: | ---: | ---: |
| gpt-6-luna | 8 tasks, 2 starts | 2 / 2 | 0 / 2 | 2 / 2 |
| gpt-6.2-astra | 8 tasks, 2 starts | 2 / 2 | 0 / 2 | 2 / 2 |
| gpt-6.2-sol | 8 tasks, 2 starts | 2 / 2 | 0 / 2 | 2 / 2 |
| gpt-6.1-terra | 8 tasks, 2 starts | 2 / 2 | 2 / 2 | 2 / 2 |

## Selections in every assigned block

Pairs give the selected implementation for displayed value A followed by displayed value B. A dash indicates a missing decision. Values are scenario-specific: A and B denote different conventions for each task.

| Model | Task | Start | No output | Anonymous | Named | Required |
| --- | --- | --- | --- | --- | --- | --- |
| gpt-6-luna | calendar | A | — | — / — | — / — | — / — |
| gpt-6-luna | calendar | B | — | — / — | — / — | — / — |
| gpt-6-luna | dedup | A | — | — / — | — / — | — / — |
| gpt-6-luna | dedup | B | — | — / — | — / — | — / — |
| gpt-6-luna | distance | A | — | — / — | — / — | — / — |
| gpt-6-luna | distance | B | — | — / — | — / — | — / — |
| gpt-6-luna | fields | A | — | — / — | — / — | — / — |
| gpt-6-luna | fields | B | B | A / B | B / B | A / B |
| gpt-6-luna | flatten | A | — | — / — | — / — | — / — |
| gpt-6-luna | flatten | B | — | — / — | — / — | — / — |
| gpt-6-luna | moving_sum | A | A | A / B | A / A | A / B |
| gpt-6-luna | moving_sum | B | — | — / — | — / — | — / — |
| gpt-6-luna | quotient | A | — | — / — | — / — | — / — |
| gpt-6-luna | quotient | B | — | — / — | — / — | — / — |
| gpt-6-luna | range | A | — | — / — | — / — | — / — |
| gpt-6-luna | range | B | — | — / — | — / — | — / — |
| gpt-6.1-terra | calendar | A | — | — / — | — / — | — / — |
| gpt-6.1-terra | calendar | B | B | A / B | A / B | A / B |
| gpt-6.1-terra | dedup | A | — | — / — | — / — | — / — |
| gpt-6.1-terra | dedup | B | — | — / — | — / — | — / — |
| gpt-6.1-terra | distance | A | — | — / — | — / — | — / — |
| gpt-6.1-terra | distance | B | — | — / — | — / — | — / — |
| gpt-6.1-terra | fields | A | — | — / — | — / — | — / — |
| gpt-6.1-terra | fields | B | — | — / — | — / — | — / — |
| gpt-6.1-terra | flatten | A | A | A / B | A / B | A / B |
| gpt-6.1-terra | flatten | B | — | — / — | — / — | — / — |
| gpt-6.1-terra | moving_sum | A | — | — / — | — / — | — / — |
| gpt-6.1-terra | moving_sum | B | — | — / — | — / — | — / — |
| gpt-6.1-terra | quotient | A | — | — / — | — / — | — / — |
| gpt-6.1-terra | quotient | B | — | — / — | — / — | — / — |
| gpt-6.1-terra | range | A | — | — / — | — / — | — / — |
| gpt-6.1-terra | range | B | — | — / — | — / — | — / — |
| gpt-6.2-astra | calendar | A | — | — / — | — / — | — / — |
| gpt-6.2-astra | calendar | B | — | — / — | — / — | — / — |
| gpt-6.2-astra | dedup | A | — | — / — | — / — | — / — |
| gpt-6.2-astra | dedup | B | — | — / — | — / — | — / — |
| gpt-6.2-astra | distance | A | — | — / — | — / — | — / — |
| gpt-6.2-astra | distance | B | — | — / — | — / — | — / — |
| gpt-6.2-astra | fields | A | — | — / — | — / — | — / — |
| gpt-6.2-astra | fields | B | — | — / — | — / — | — / — |
| gpt-6.2-astra | flatten | A | — | — / — | — / — | — / — |
| gpt-6.2-astra | flatten | B | — | — / — | — / — | — / — |
| gpt-6.2-astra | moving_sum | A | — | — / — | — / — | — / — |
| gpt-6.2-astra | moving_sum | B | — | — / — | — / — | — / — |
| gpt-6.2-astra | quotient | A | A | A / B | A / A | A / B |
| gpt-6.2-astra | quotient | B | — | — / — | — / — | — / — |
| gpt-6.2-astra | range | A | — | — / — | — / — | — / — |
| gpt-6.2-astra | range | B | B | A / B | B / B | A / B |
| gpt-6.2-sol | calendar | A | — | — / — | — / — | — / — |
| gpt-6.2-sol | calendar | B | — | — / — | — / — | — / — |
| gpt-6.2-sol | dedup | A | A | A / B | A / A | A / B |
| gpt-6.2-sol | dedup | B | — | — / — | — / — | — / — |
| gpt-6.2-sol | distance | A | — | — / — | — / — | — / — |
| gpt-6.2-sol | distance | B | B | A / B | B / B | A / B |
| gpt-6.2-sol | fields | A | — | — / — | — / — | — / — |
| gpt-6.2-sol | fields | B | — | — / — | — / — | — / — |
| gpt-6.2-sol | flatten | A | — | — / — | — / — | — / — |
| gpt-6.2-sol | flatten | B | — | — / — | — / — | — / — |
| gpt-6.2-sol | moving_sum | A | — | — / — | — / — | — / — |
| gpt-6.2-sol | moving_sum | B | — | — / — | — / — | — / — |
| gpt-6.2-sol | quotient | A | — | — / — | — / — | — / — |
| gpt-6.2-sol | quotient | B | — | — / — | — / — | — / — |
| gpt-6.2-sol | range | A | — | — / — | — / — | — / — |
| gpt-6.2-sol | range | B | — | — / — | — / — | — / — |

The primary comparison is required versus anonymous in the same model, task and start. A single choice per prompt and eight authored mechanisms limit inference about other tasks and systems. Unobserved blocks remain in the scheduled denominator.

Offline recount: `python3 -I analysis/output_provenance_report.py analysis/output_provenance_20261128 --check`.
