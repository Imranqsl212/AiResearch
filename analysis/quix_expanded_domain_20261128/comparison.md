# Expanded-domain transfer of selected QuixBugs expressions

| Study | Output condition | Valid decisions | Previously passing target assessments | Also pass expanded domain | Lost on expanded domain |
| --- | --- | ---: | ---: | ---: | ---: |
| free_patch | none | 16 | 15 | 15 | 0 |
| free_patch | shared | 16 | 16 | 16 | 0 |
| free_patch | revealing | 16 | 16 | 16 | 0 |
| reversal | concealed | 16 | 16 | 16 | 0 |
| reversal | upstream | 16 | 13 | 13 | 0 |
| reversal | alternative | 16 | 13 | 13 | 0 |

Distinct task-specific parsed expressions across the two ledgers: 9. Different choices can return the same program. Any lost-target witness is saved in results.json. No model calls are made.

| Task | Original inputs distinguishing the targets | New inputs distinguishing the targets | Ideal correctness after one / three random original examples |
| --- | ---: | ---: | ---: |
| is_valid_parenthesization | 19/63 | 441/1982 | 0.651 / 0.830 |
| knapsack | 117/240 | 1522/3060 | 0.744 / 0.933 |
| max_sublist_sum | 32/121 | 3185/5460 | 0.632 / 0.801 |
| quicksort | 105/121 | 5396/5460 | 0.934 / 0.999 |

The ideal-observer calculation assumes two equally likely deterministic contracts, independent uniform inputs with replacement, and availability of a program implementing either contract. It is an analytical ceiling under those assumptions. The experiment deliberately chose examples distinguishing the contracts.

Reproduce with `python3 -B -m analysis.quix_expanded_domain check`.
