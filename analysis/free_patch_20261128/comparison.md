# Writing a replacement expression on QuixBugs

Each of four algorithms contributes an upstream defective and corrected starting program. Two hosted model configurations received each start under three displays. Only a valid returned implementation is scored. A submitted expression has to pass every held-out input for that task.

| Current-program output | Scored / scheduled | Defective starts repaired | Working starts preserved | Replacements | Passing replacements differing from upstream patch AST |
| --- | ---: | ---: | ---: | ---: | ---: |
| none | 16/16 | 7/8 | 8/8 | 7 | 0 |
| shared | 16/16 | 8/8 | 8/8 | 8 | 0 |
| revealing | 16/16 | 8/8 | 8/8 | 8 | 0 |

Status of every scheduled decision: OK 48.

| Revealing vs no output, matched starts | Both pass | Revealing only | No output only | Neither | Missing / scheduled pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| faulty | 7 | 1 | 0 | 0 | 0/8 |
| working | 8 | 0 | 0 | 0 | 0/8 |

| Task | Finite held-out inputs | Passed by original defect | Passed by upstream correction |
| --- | ---: | ---: | ---: |
| is_valid_parenthesization | 63 | 44 | 63 |
| knapsack | 240 | 123 | 240 |
| max_sublist_sum | 121 | 89 | 121 |
| quicksort | 121 | 16 | 121 |

This measures free expression generation in an identified slot of four published benchmark tasks. It does not measure fault localization, repository editing, frequency of production defects, or functional correctness outside the finite domains. Public benchmark familiarity is possible. The 16 model-by-start blocks contain four distinct defects. Each model made at most one decision for each condition.

Run the offline recount with `python3 -B -m analysis.free_patch_report --check`.
