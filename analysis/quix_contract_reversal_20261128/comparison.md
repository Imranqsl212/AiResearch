# Can the same code be repaired in opposite directions?

Four published benchmark defects each implement a coherent neighboring specification on the independently graded finite domain. The two target prompts have the same source, two rule descriptions, action grammar and input. Only the required output changes. Each model authors an expression or keeps the current one.

| Target shown | Scored calls / scheduled | Repaired starts | Preserved starts | Final program implements upstream / alternative / neither |
| --- | ---: | ---: | ---: | ---: |
| concealed | 16/16 | 3/16 | 13/16 | 7 / 9 / 0 |
| upstream | 16/16 | 7/8 | 6/8 | 13 / 3 / 0 |
| alternative | 16/16 | 7/8 | 6/8 | 3 / 13 / 0 |

Both targets elicited the correct program in 10/16 complete blocks. Allowing for missing outcomes, the count over all 16 scheduled blocks lies between 10 and 10. In complete blocks, both answers were reversed in 0, both implemented the upstream convention in 3, both implemented the alternative in 3, and at least one implemented neither in 0.

| Task | Held-out inputs | Inputs distinguishing rival contracts | Required target answers (upstream / alternative) |
| --- | ---: | ---: | --- |
| is_valid_parenthesization | 63 | 19 | false / true |
| knapsack | 240 | 117 | 19 / 11 |
| max_sublist_sum | 121 | 32 | 7 / 0 |
| quicksort | 121 | 105 | [-2, 8, 8] / [-2, 8] |

One concealed reply is scored against both possible contracts. The incompatible held-out outputs imply at most one pass per response. A third program may fail both. Frequencies of canonical and alternative choices cannot isolate prior model exposure. The neighboring contracts were identified by inspecting the historical faulty implementations.

Offline replay: `python3 -B -m analysis.quix_contract_reversal_report --check`.
