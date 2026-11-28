# Grading the new target with the published QuixBugs tests

| Task | Default / published cases | Distinguish contracts | Overlap with original grading inputs | Overlap with displays |
| --- | ---: | ---: | ---: | ---: |
| is_valid_parenthesization | 3/3 | 1 | 2 | 0 |
| knapsack | 9/10 | 6 | 0 | 0 |
| max_sublist_sum | 6/6 | 4 | 0 | 0 |
| quicksort | 13/13 | 1 | 0 | 0 |

Both prompts name the two possible contracts. This table covers calls with one identified target and a usable expression.

| Assigned target | Assigned and published pass | Assigned pass only | Published pass only | Neither |
| --- | ---: | ---: | ---: | ---: |
| upstream | 13 | 0 | 0 | 3 |
| alternative | 0 | 13 | 3 | 0 |

The suite implements the benchmark's original requirement. An expression can satisfy the assigned alternative and fail a published test. The disabled 24-item knapsack slow case is recorded but unevaluated. The public cases are additional external evidence on this panel; the overlap columns identify examples used elsewhere. The four tasks and their published tests are a selected set.

Pinned [benchmark test cases](https://github.com/jkoppel/QuixBugs/tree/4257f44b0ff1181dedaedee6a447e133219fcebf/json_testcases).
