# What does revealing the required answer add to seeing the same execution?

Each block fixes the model, task, starting code, edit menu and probe input. Actual output comes from the current implementation. Required output comes from the target contract. Each independently varies between staying hidden and being displayed. The wording either names the target rule explicitly or leaves it hidden.

## Choices by initial correctness

| Written rule | Evidence shown | Valid / scheduled native calls | Repaired / scored / assigned | Preserved / scored / assigned |
| --- | --- | ---: | ---: | ---: |
| hidden | none | 6 / 12 | 0 / 6 / 12 | 6 / 6 / 12 |
| hidden | actual | 6 / 12 | 1 / 6 / 12 | 5 / 6 / 12 |
| hidden | required | 12 / 24 | 6 / 6 / 12 | 6 / 6 / 12 |
| hidden | both | 12 / 24 | 6 / 6 / 12 | 6 / 6 / 12 |
| explicit | none | 12 / 24 | 6 / 6 / 12 | 6 / 6 / 12 |
| explicit | actual | 12 / 24 | 6 / 6 / 12 | 6 / 6 / 12 |
| explicit | required | 12 / 24 | 6 / 6 / 12 | 6 / 6 / 12 |
| explicit | both | 12 / 24 | 6 / 6 / 12 | 6 / 6 / 12 |

84 valid native choices yield 96 target assessments. Under the hidden wording, each no-display or actual-only choice is assessed under both contracts. Its program passes exactly one contract. The pooled 50% score and absence of any pooled choice that satisfies both targets follow from this design. The relative proportions of repairs and preserved starts depend on the choices.

Missing calls: UNSTARTED=84.

## Matched changes

For the same target, a gain means that only the second arm passes. A loss means that only the first arm passes. Bounds give the possible net change in the count of passing cases over all assigned pairs if every missing answer is assigned either permitted implementation.

| Written rule | Evidence change | Start | Complete / assigned | Gains | Losses | Net bounds (count) |
| --- | --- | --- | ---: | ---: | ---: | --- |
| hidden | actual to both | repair | 6 / 12 | 5 | 0 | [-1, +11] |
| hidden | actual to both | preservation | 6 / 12 | 1 | 0 | [-5, +7] |
| hidden | none to required | repair | 6 / 12 | 6 | 0 | [+0, +12] |
| hidden | none to required | preservation | 6 / 12 | 0 | 0 | [-6, +6] |
| hidden | required to both | repair | 6 / 12 | 0 | 0 | [-6, +6] |
| hidden | required to both | preservation | 6 / 12 | 0 | 0 | [-6, +6] |
| hidden | none to actual | repair | 6 / 12 | 1 | 0 | [-5, +7] |
| hidden | none to actual | preservation | 6 / 12 | 0 | 1 | [-7, +5] |
| explicit | actual to both | repair | 6 / 12 | 0 | 0 | [-6, +6] |
| explicit | actual to both | preservation | 6 / 12 | 0 | 0 | [-6, +6] |
| explicit | none to required | repair | 6 / 12 | 0 | 0 | [-6, +6] |
| explicit | none to required | preservation | 6 / 12 | 0 | 0 | [-6, +6] |
| explicit | required to both | repair | 6 / 12 | 0 | 0 | [-6, +6] |
| explicit | required to both | preservation | 6 / 12 | 0 | 0 | [-6, +6] |
| explicit | none to actual | repair | 6 / 12 | 0 | 0 | [-6, +6] |
| explicit | none to actual | preservation | 6 / 12 | 0 | 0 | [-6, +6] |

The actual-to-both contrast adds the required answer with the execution message held fixed. Its matched increment under hidden wording minus its matched increment under explicit wording is:
- Repair: net +5 across 6 complete four-cell comparisons; bounds [-7, +17] across all 12 blocks.
- Preservation: net +1 across 6 complete four-cell comparisons; bounds [-11, +13] across all 12 blocks.

Within each wording, the factorial interaction compares the gain from adding the required output when actual output was shown against the gain when actual output was withheld. Each complete four-cell comparison concerns the same target and starting code.

| Written rule | Start | Complete blocks | Net interaction across complete blocks | Bounds across assigned blocks |
| --- | --- | ---: | ---: | --- |
| hidden | repair | 6 | -1 | [-13, +11] |
| hidden | preservation | 6 | +1 | [-11, +13] |
| explicit | repair | 6 | +0 | [-12, +12] |
| explicit | preservation | 6 | +0 | [-12, +12] |

## Directional tracking of two opposing target rules

A complete block tracks both target rules when its chosen implementation passes for target A and its other choice passes for target B on the same task, start, model and probe input.

| Written rule | Evidence shown | Both correct / complete blocks | Both wrong | Bounds for both-correct count |
| --- | --- | ---: | ---: | --- |
| hidden | none | 0 / 6 | 0 | [0, 0] |
| hidden | actual | 0 / 6 | 0 | [0, 0] |
| hidden | required | 6 / 6 | 0 | [6, 12] |
| hidden | both | 6 / 6 | 0 | [6, 12] |
| explicit | none | 6 / 6 | 0 | [6, 12] |
| explicit | actual | 6 / 6 | 0 | [6, 12] |
| explicit | required | 6 / 6 | 0 | [6, 12] |
| explicit | both | 6 / 6 | 0 | [6, 12] |

## Identical displayed values on working starts

This additional descriptive comparison was specified after the collection protocol was frozen. On working starts the actual output and the required answer are identical for the fixed input. The actual-only and required-only prompts differ solely in the text identifying the displayed value as the program's observed output or the installation's required output. On these tasks each choice uniquely identifies the implementation. A change in final correctness therefore also identifies a change of source.

| Written rule | Complete / assigned working starts | Only required preserves | Only actual preserves | Both preserve | Neither preserves |
| --- | ---: | ---: | ---: | ---: | ---: |
| hidden | 6 / 12 | 1 | 0 | 5 | 0 |
| explicit | 6 / 12 | 0 | 0 | 6 | 0 |

## Every matched hidden-rule block

Letters identify the selected implementation, shown for target A then B. Entries under neither and actual repeat the same native choice across the two targets. A dash marks a missing native response.

| Model | Task | Start | Neither | Actual | Required | Both |
| --- | --- | --- | --- | --- | --- | --- |
| gpt-6-luna | argmax | A | A / A | A / A | A / B | A / B |
| gpt-6-luna | argmax | B | — / — | — / — | — / — | — / — |
| gpt-6-luna | round | A | — / — | — / — | — / — | — / — |
| gpt-6-luna | round | B | B / B | A / A | A / B | A / B |
| gpt-6-luna | sort | A | — / — | — / — | — / — | — / — |
| gpt-6-luna | sort | B | B / B | B / B | A / B | A / B |
| gpt-6.2-astra | argmax | A | — / — | — / — | — / — | — / — |
| gpt-6.2-astra | argmax | B | B / B | B / B | A / B | A / B |
| gpt-6.2-astra | round | A | A / A | A / A | A / B | A / B |
| gpt-6.2-astra | round | B | — / — | — / — | — / — | — / — |
| gpt-6.2-astra | sort | A | A / A | A / A | A / B | A / B |
| gpt-6.2-astra | sort | B | — / — | — / — | — / — | — / — |

The two models and opposing contracts do not supply independent repetitions of the three authored tasks. Each block contributes one sampled choice per distinct prompt. Naming the contract in the explicit wording makes its required output redundant for identifying the rule. Binding the new display to the same probe narrows the interpretation of the evidence contrast. On a faulty start with a revealing input, the actual and required outputs themselves differ; changing from one to the other cannot isolate a pure label effect.

To recount offline, run `python3 -I analysis/feedback_factorial_report.py analysis/feedback_factorial_20261128 --check` from the repository or extracted reviewer packet.
