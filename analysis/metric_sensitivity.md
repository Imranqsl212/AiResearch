# Metric sensitivity plan and implemented engineering checks

**No empirical sensitivity results exist:** there are zero eligible agent runs. `analysis/sensitivity.py` computes run-level alternative definitions without p-values or raw-data mutation; its unit test confirms that one observed repeat is persistence under threshold 1 but not under the preregistered threshold 2 or the threshold-3 sensitivity rule. These synthetic cases are explicitly engineering-only.

| Construct | Primary or strict definition | Alternative/proxy | Interpretation constraint |
| --- | --- | --- | --- |
| Persistence | Two consecutive coded non-informative repeats after verified index failure. | Thresholds 1 and 3. | Unknown coding breaks a streak; if no positive streak and coding is incomplete, status is `NOT_ASSESSABLE`. |
| Strategy change | Comparable structured `strategy_class` transition after failure. | Tool and `hypothesis_id` switches displayed separately. | These are different constructs, not interchangeable estimates. Semantic-distance transition requires a validated coder and is NOT IMPLEMENTED. |
| Repetition | Adjacent exact canonical action signatures. | Coded semantic non-informative repeat. | May disagree for paraphrased or context-dependent actions; both denominators must be shown. |
| Stopping | Explicit `AGENT_SELF_TERMINATION` event and evaluator receipt. | Any `RUN_FINISHED` record. | The latter is deliberately an invalid voluntary-stop proxy; disagreement exposes forced endings. |
| Progress | Per-action independent verifier witness where available. | `EFFECT_CONFIRMED` in a tool observation. | Observation is not independent ground truth; H2's 12-action recovery endpoint remains unassessable without a timed verifier witness. |
| Success | Passing, concordant terminal verifier. | Agent success claim. | A claim is evidence about communication, not target state. |

H1 uses unbounded recovery after meaningful adaptation; H2 adds a twelve-action window. A positive score for either needs an evaluator-origin goal witness on the same logical-action timeline after adaptation. With only a final verifier, positive H1/H2 recovery is `NOT_ASSESSABLE`, not a late-success proxy. Fully observed immediate non-success stops remain zeros in the recovery denominator, while infrastructure aborts are excluded from behavior and retained in an audit table. The pipeline now emits a separately labeled H1 sensitivity that zero-fills planned paired family-condition cells with no eligible exposed run; it does not impute missing run slots within an observed cell. Future reporting still needs family-level disagreements, missing coding by condition, failure exposure, forced-stop censoring, and broader missingness-pattern analyses before any narrative conclusion. If a conclusion reverses across defensible definitions, report it as definition-dependent rather than choosing the favorable one.

**Precollection forced-stop check (2026-09-29):** the terminal task-state
receipt and terminal stop cause are separate. A budget/timeout episode after
the frozen index failure is not missing by default: RD contributes zero when
the independent receipt confirms no goal, and UD contributes zero to the
agent-initiated justified-stop endpoint. A verified terminal goal plus an
ordered action-time witness can still establish RD recovery before forced
termination; the forced stop is retained as its own outcome. Unknown task
state remains unassessable. Synthetic tests cover all four branches and the
family-level H1 denominator. This does not estimate an agent effect.
