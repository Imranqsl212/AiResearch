# What changed in the repaired maintenance functions?

Each counted implementation must pass the stated component on every held-out case. A single functional pass requires both components. The block ledger in component_scores.json includes the number passing out of 45 inputs (tqdm) or 96 (Matplotlib), plus the first failing input for each component.

| Project and component | No execution | Shared execution | Revealing execution |
| --- | ---: | ---: | ---: |
| tqdm / index_value_pairs | 4/4 | 4/4 | 4/4 |
| tqdm / progress_forwarding | 4/4 | 4/4 | 4/4 |
| matplotlib / direction_preserved | 3/4 | 4/4 | 3/4 |
| matplotlib / interval_extent | 3/4 | 4/4 | 2/4 |

| Matplotlib model and starting state | Display | Ascending, expanding / contained | Descending, expanding / contained |
| --- | --- | ---: | ---: |
| gpt-6.2-astra / working | shared | 42/42 and 6/6 | 42/42 and 6/6 |
| gpt-6.2-astra / working | revealing | 42/42 and 6/6 | 42/42 and 6/6 |
| gpt-6.2-astra / working | none | 42/42 and 6/6 | 42/42 and 6/6 |
| gpt-6-luna / faulty | shared | 42/42 and 6/6 | 42/42 and 6/6 |
| gpt-6-luna / faulty | none | 42/42 and 6/6 | 10/42 and 0/6 |
| gpt-6-luna / faulty | revealing | 42/42 and 6/6 | 10/42 and 0/6 |
| gpt-6-luna / working | revealing | 42/42 and 6/6 | 8/42 and 6/6 |
| gpt-6-luna / working | none | 42/42 and 6/6 | 42/42 and 6/6 |
| gpt-6-luna / working | shared | 42/42 and 6/6 | 42/42 and 6/6 |
| gpt-6.2-astra / faulty | shared | 42/42 and 6/6 | 42/42 and 6/6 |
| gpt-6.2-astra / faulty | none | 42/42 and 6/6 | 42/42 and 6/6 |
| gpt-6.2-astra / faulty | revealing | 42/42 and 6/6 | 42/42 and 6/6 |

Expanding means that at least one requested endpoint lies outside the old interval. Contained requests leave the interval unchanged under the contract. This post-hoc decomposition grades all matched programs.

### Do the displayed inputs reveal the selected faults?

The labels shared and revealing were fixed against the historical parent defect. For every distinct final expression that fails the held-out contract, the table replays both displays. The ledger includes all passing and failing expressions.

| Project and failing expression | Shared input: historical / selected / expected output | Revealing input: historical / selected / expected output | Held-out failures: historical only / selected only / both / neither | Cases with three distinct outputs |
| --- | --- | --- | --- | ---: |
| matplotlib / (max(vmin, vmax, oldmax), min(vmin, vmax, oldmin)) | [10, 0] / [10, 0] / [10, 0] | [7, 3] / [7, 3] / [8, 2] | 0 / 0 / 38 / 58 | 0 |
| matplotlib / (max(oldmin, min(vmin, vmax)), min(oldmax, max(vmin, vmax))) | [10, 0] / [8, 2] / [10, 0] | [7, 3] / [8, 2] / [8, 2] | 14 / 10 / 24 / 48 | 24 |

The original tqdm defect returned all expected pairs on 17/45 inputs and forwarded the wrapper on 45/45. The deliberately bypassing expression, enumerate(iterable, start), returned all pairs on 45/45 and forwarded the wrapper on 0/45. This last row is a scripted control, not a model decision.

Progress forwarding requires one observed wrapper for the original iterable, actual iteration of that wrapper and preservation of the supplied keyword options in the recording fixture. This does not test progress rendering. Matplotlib separates axis direction from the exact extent of the extended interval.

Replay with `python3 -B -m analysis.production_patch_components --check`.
