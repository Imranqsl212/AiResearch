# Does explaining output selection change which program an agent chooses?

Both arms show the identical input and value as an observation from one unnamed candidate. The disclosure arm also describes how the value was selected. Neither displayed value identifies the installation's required convention. Tracking both means choosing the producing implementation on both native calls.

| Caption | Valid / assigned calls | Both values followed / complete blocks | Both opposed | Always kept | Always switched | Bounds on both-follow count |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| anonymous | 0 / 16 | 0 / 0 | 0 | 0 | 0 | [0, 8] |
| disclosed | 0 / 16 | 0 / 0 | 0 | 0 | 0 | [0, 8] |

Across 0/8 complete matched blocks, both captions tracked both values in 0. Only anonymous tracked both in 0, only disclosed in 0, and neither in 0. The possible change in the number tracking both under disclosed minus anonymous is [-8, +8] over all eight assignments.

Signed tracking gives +1 to both-follow, −1 to both-opposed, and 0 to a constant selection. The change in this signed total was +0 across 0 complete comparisons, with bounds [-16, +16] across the eight assigned blocks.

| Caption | Repair / scored | Preservation / scored | Signed total / complete blocks |
| --- | ---: | ---: | ---: |
| anonymous | 0 / 0 | 0 / 0 | +0 / 0 |
| disclosed | 0 / 0 | 0 / 0 | +0 / 0 |

Each native choice is assessed once per possible hidden target. Exactly one of the two assessments must pass for each valid response. These paired target grades are not two independent decisions. Each task appears once in the eight blocks, so model and task are not fully crossed. Each native call supplies one sampled response.

Missing calls: UNSTARTED=32.

| Model | Task | Initial implementation | Anonymous selections for A / B | Disclosed selections for A / B |
| --- | --- | --- | --- | --- |
| gpt-6-luna | fields | B | — / — | — / — |
| gpt-6-luna | moving_sum | A | — / — | — / — |
| gpt-6.1-terra | calendar | B | — / — | — / — |
| gpt-6.1-terra | flatten | A | — / — | — / — |
| gpt-6.2-astra | quotient | A | — / — | — / — |
| gpt-6.2-astra | range | B | — / — | — / — |
| gpt-6.2-sol | dedup | A | — / — | — / — |
| gpt-6.2-sol | distance | B | — / — | — / — |

Offline recount: `python3 -B -m analysis.selection_disclosure_report --check`.
