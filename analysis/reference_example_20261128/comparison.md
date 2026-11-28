# Response to a trusted reference example

Two models each received both starting implementations for three authored tasks. Each distinguishing pair shows the same input and changes only the required output. All scores refer to the six held-out cases for the assigned contract.

| Reference example | Valid / scheduled native calls | Defective starts repaired / assessed / scheduled | Working starts preserved / assessed / scheduled |
| --- | ---: | ---: | ---: |
| none | 12 / 12 | 2 / 12 / 12 | 10 / 12 / 12 |
| shared | 12 / 12 | 3 / 12 / 12 | 9 / 12 / 12 |
| revealing | 24 / 24 | 12 / 12 / 12 | 12 / 12 / 12 |

Both revealing responses selected the correct implementation in 12/12 complete blocks. Among 12 scheduled blocks, the lower and upper counts allowing for missing responses are 12 and 12. Both responses were wrong in 0 complete blocks. The action was keep both times in 0 and switch both times in 0.

For the no-example and shared-example controls, each native response is assessed against both possible target contracts. Exactly half of these assessments must pass because each supplied implementation satisfies exactly one contract. This proportion is fixed by the design. The empirical endpoint measures paired, correct responses when the authoritative output changes. The tasks require selecting between two supplied functions. The CPython pilot displayed execution of the current candidate, whereas this control supplies a required output from the target specification.
