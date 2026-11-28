# When did the selected contract change?

Both sessions in each pair see identical source and the same input. Only the required output changes. Each pair comprises distinct native calls.

| Group | Pairs | Both targets followed | Upstream target passed | Alternative target passed | Same selected syntax | Same starting contract on both | Same nonstarting contract on both |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 16 | 10 | 13 | 13 | 6 | 2 | 4 |
| gpt-6-luna | 8 | 2 | 5 | 5 | 6 | 2 | 4 |
| gpt-6.2-astra | 8 | 8 | 8 | 8 | 0 | 0 | 0 |
| is_valid_parenthesization | 4 | 3 | 3 | 4 | 1 | 0 | 1 |
| knapsack | 4 | 2 | 3 | 3 | 2 | 0 | 2 |
| max_sublist_sum | 4 | 2 | 3 | 3 | 2 | 2 | 0 |
| quicksort | 4 | 3 | 4 | 3 | 1 | 0 | 1 |
| faulty | 8 | 5 | 7 | 6 | 3 | 1 | 2 |
| working | 8 | 5 | 6 | 7 | 3 | 1 | 2 |

A pair that implements the same nonstarting contract on both targets changes the starting behavior in both calls. It is one of the ways target-invariant responses can arise. The model, source and task strata share the same 16 pairs. Each model-specific rate describes this benchmark panel in this run.

| Task | Selected expression | Matching historical syntax | Decisions |
| --- | --- | --- | ---: |
| is_valid_parenthesization | True | faulty | 3 |
| is_valid_parenthesization | depth == 0 | working | 4 |
| is_valid_parenthesization | depth >= 0 | neither | 5 |
| knapsack | weight < j | faulty | 6 |
| knapsack | weight <= j | working | 6 |
| max_sublist_sum | max(0, max_ending_here + x) | working | 6 |
| max_sublist_sum | max_ending_here + x | faulty | 6 |
| quicksort | x > pivot | faulty | 5 |
| quicksort | x >= pivot | working | 7 |

The only additional syntax in this panel is depth >= 0. In the pinned function every step producing a negative depth returns False immediately, so reaching the final return guarantees depth >= 0. At that location the expression is equivalent to the historical return True on any finite parentheses string. The eight other task–expression pairs are the historical sources themselves.

Replay with `python3 -B -m analysis.quix_contract_matched_pairs`.
