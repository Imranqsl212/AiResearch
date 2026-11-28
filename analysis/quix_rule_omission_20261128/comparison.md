# What changes when the contract descriptions are removed?

Sixteen original QuixBugs model–task–start blocks receive both opposing target examples again. The two complete descriptions of the conventions were deleted; the source, localized expression, other instructions and displayed input/output for each target were held fixed. This later cohort uses independent fresh responses. A single input/output example can support functions outside both reference classes. Each classification below concerns the two fixed finite reference domains.

| Rule descriptions | Tracks both targets / complete blocks | Both reversed | Always upstream | Always alternative | At least one neither | Bounds across all 16 blocks |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| named | 10 / 16 | 0 | 3 | 3 | 0 | [10, 10] |
| omitted | 5 / 9 | 0 | 3 | 0 | 1 | [5, 12] |

## Matched successes

Only named and only omitted count opposite discordances. Bounds give the net number of successes under omission minus the number when rules were named over the scheduled comparisons. The primary endpoint requires success under both opposite target outputs in the same block.

| Endpoint | Complete / 16 | Both succeed | Only named | Only omitted | Neither succeeds | Bounds on net change |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| both_targets | 9 / 16 | 5 | 0 | 0 | 4 | [-5, +2] |
| upstream | 9 / 16 | 6 | 0 | 3 | 0 | [-4, +3] |
| alternative | 9 / 16 | 5 | 3 | 0 | 1 | [-8, -1] |

## Final scored implementations

| Rule descriptions | Required target | Valid / scheduled calls | Repaired / scored / assigned | Preserved / scored / assigned | Implements upstream / alternative / neither |
| --- | --- | ---: | ---: | ---: | ---: |
| named | upstream | 16 / 16 | 7 / 8 / 8 | 6 / 8 / 8 | 13 / 3 / 0 |
| named | alternative | 16 / 16 | 7 / 8 / 8 | 6 / 8 / 8 | 3 / 13 / 0 |
| omitted | upstream | 9 / 16 | 5 / 5 / 8 | 4 / 4 / 8 | 9 / 0 / 0 |
| omitted | alternative | 9 / 16 | 2 / 4 / 8 | 3 / 5 / 8 | 3 / 5 / 1 |

Native statuses under named descriptions: OK=32.

Native statuses under omitted descriptions: OK=18, UNSTARTED=14.

## Fit to the displayed example

This supplementary check executes each graded expression on the single input in its prompt. The primary endpoint above uses only held-out cases. The two checks can disagree.

| Descriptions | Required target | Pass example and held-out target | Example only | Held-out target only | Fail both |
| --- | --- | ---: | ---: | ---: | ---: |
| named | upstream | 13 | 0 | 0 | 3 |
| named | alternative | 13 | 0 | 0 | 3 |
| omitted | upstream | 9 | 0 | 0 | 0 |
| omitted | alternative | 5 | 1 | 0 | 3 |

## Every matched block

The two entries in each column are the reference behaviors implemented for the upstream and alternative displayed values, respectively. A non-OK native status is shown verbatim.

| Model, task and source | Named descriptions | Omitted descriptions |
| --- | --- | --- |
| gpt-6-luna_is_valid_parenthesization_faulty | upstream / alternative | upstream / alternative |
| gpt-6-luna_is_valid_parenthesization_working | alternative / alternative | upstream / neither |
| gpt-6-luna_knapsack_faulty | upstream / upstream | UNSTARTED / UNSTARTED |
| gpt-6-luna_knapsack_working | alternative / alternative | upstream / upstream |
| gpt-6-luna_max_sublist_sum_faulty | alternative / alternative | upstream / upstream |
| gpt-6-luna_max_sublist_sum_working | upstream / upstream | UNSTARTED / UNSTARTED |
| gpt-6-luna_quicksort_faulty | upstream / upstream | upstream / upstream |
| gpt-6-luna_quicksort_working | upstream / alternative | UNSTARTED / UNSTARTED |
| gpt-6.2-astra_is_valid_parenthesization_faulty | upstream / alternative | UNSTARTED / UNSTARTED |
| gpt-6.2-astra_is_valid_parenthesization_working | upstream / alternative | UNSTARTED / UNSTARTED |
| gpt-6.2-astra_knapsack_faulty | upstream / alternative | upstream / alternative |
| gpt-6.2-astra_knapsack_working | upstream / alternative | UNSTARTED / UNSTARTED |
| gpt-6.2-astra_max_sublist_sum_faulty | upstream / alternative | upstream / alternative |
| gpt-6.2-astra_max_sublist_sum_working | upstream / alternative | upstream / alternative |
| gpt-6.2-astra_quicksort_faulty | upstream / alternative | UNSTARTED / UNSTARTED |
| gpt-6.2-astra_quicksort_working | upstream / alternative | upstream / alternative |

Outcomes can also vary between repeated sampling sessions; the named and omitted cohorts were run at different times. Neither four challenge algorithms nor a single example per algorithm establish semantic generalization outside the scored domains.

Recount offline with `python3 -B -m analysis.quix_rule_omission_report --check`.
