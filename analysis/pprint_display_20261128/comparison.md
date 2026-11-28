# What changed when the agent saw fresh execution output?

On one CPython dictionary-formatting task, each of 16 archived first-edit histories received one further decision under each display condition. The model, code, prior exchange and available edits were held fixed within each history. Every branch retained any diagnostic already present in that exchange.

- Shared output used the input `{7: 'cobalt', 3: 'amber'}`.
- Revealing output used the input `{20: 'cobalt', 3: 'amber'}`.

## Repair and preservation

Repair starts from faulty code, and preservation starts from working code. A replacement can preserve functionality. Success is a pass on all ten held-out checks. Correctness fractions use scored decisions within their starting stratum. The scored/scheduled column includes both strata. A dash indicates an empty denominator.

| Model | New display | Scored/scheduled | Faults repaired | Working states preserved | Working states damaged | Working states rewritten and still passing |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| All | No new output | 16/16 | 2/4 | 12/12 | 0/12 | 4/12 |
| All | Shared output | 16/16 | 4/4 | 12/12 | 0/12 | 3/12 |
| All | Revealing output | 16/16 | 4/4 | 12/12 | 0/12 | 4/12 |
| gpt-6-luna | No new output | 8/8 | 2/4 | 4/4 | 0/4 | 1/4 |
| gpt-6-luna | Shared output | 8/8 | 4/4 | 4/4 | 0/4 | 1/4 |
| gpt-6-luna | Revealing output | 8/8 | 4/4 | 4/4 | 0/4 | 2/4 |
| gpt-6.2-astra | No new output | 8/8 | — | 8/8 | 0/8 | 3/8 |
| gpt-6.2-astra | Shared output | 8/8 | — | 8/8 | 0/8 | 2/8 |
| gpt-6.2-astra | Revealing output | 8/8 | — | 8/8 | 0/8 | 2/8 |

Missing outcomes: none.

## Paired comparisons

The planned primary comparison is recovery from a faulty start under revealing versus no new output. Each contrast matches choices from the same history. Either both branches passed, only one did, or neither passed. Unavailable pairs contribute only to the scheduled denominator. The final column counts different selected implementations among complete pairs, including replacements with identical functional grades.

| First condition vs second condition | Starting state | Complete/scheduled | Both pass | Second alone passes | First alone passes | Neither passes | Different final implementations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No new output vs Revealing output | Faulty | 4/4 | 2 | 2 | 0 | 0 | 3/4 |
| No new output vs Revealing output | Working | 12/12 | 12 | 0 | 0 | 0 | 4/12 |
| No new output vs Shared output | Faulty | 4/4 | 2 | 2 | 0 | 0 | 3/4 |
| No new output vs Shared output | Working | 12/12 | 12 | 0 | 0 | 0 | 3/12 |
| Shared output vs Revealing output | Faulty | 4/4 | 4 | 0 | 0 | 0 | 2/4 |
| Shared output vs Revealing output | Working | 12/12 | 12 | 0 | 0 | 0 | 3/12 |

In 2 faulty histories both displayed conditions repaired the code and the no-output condition failed. The no-output choice retained the faulty source in 2/2. The two displayed conditions chose the same passing implementation in 2/2.

## Retrospective policy baselines

These descriptive comparisons were added after the display protocol was frozen. The three rules are computed directly on the saved checkpoints and use no model decisions from the display experiment.

| Rule on the same source menu | Faults repaired | Working states preserved |
| --- | ---: | ---: |
| Keep the post-edit source | 0/4 | 12/12 |
| Restore the source before the first edit | 4/4 | 4/12 |
| Choose a passing variant using the held-out grades | 4/4 | 12/12 |

Each menu offered four distinct implementations through one keep action and three replacements. Two implementations passed all ten tests. The last rule uses knowledge of their grades to specify an ideal upper bound. Uniform choice would have a one-half chance of passing in either stratum. That probability is determined by the menu, not estimated from model calls.

The sixteen histories include four occurrences of the same faulty edit and twelve passing checkpoints. Each fork yielded at most one response to a bounded edit menu. This exploratory comparison describes those decisions on one formatter. It does not estimate an effect across independent defects or establish equivalence between display conditions.

Reproduce from the repository root with `python3 -B -m analysis.pprint_display_report --check`. The recount verifies the plan and calibration digests, matches decisions to planned prompt digests and independently scores the recorded menu selections from the held-out grades.

[Protocol](../../docs/PPRINT_DISPLAY_20261128.md) · [Plan](plan.json) · [Functional calibration](calibration.json) · [Decision ledger](results.json)
