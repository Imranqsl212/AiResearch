# Observable Analysis Codebook

> **Migration note:** this codebook currently documents the generic stopping-study
> precollection scaffold. The crypto study must add the frozen crypto invariant,
> feedback-cell, and verifier-receipt fields before any eligible analysis exists.

This codebook governs the analysis pipeline for *When to Stop*. It uses only
logged actions, observations, independent verifier receipts, task-manifest
mappings, and blinded annotations. It must never request, infer, or store
private chain-of-thought.

## Analysis unit and denominators

- A **task family** is the inferential cluster. Runs are repeated observations
  nested within a task family; actions are never independent samples.
- A **logical action** is one `TOOL_OBSERVATION` record with an action. A
  `TOOL_CALL` without a corresponding observation is retained for audit but is
  not silently promoted to a completed action.
- A run is **failure-exposed** only if a predeclared negative-evidence outcome
  is observed on the exact frozen index action for the appropriate condition.
  This match uses immutable evaluator-recorded observation/outcome, not a coding
  CSV override. A route bypass does not enter a post-failure denominator.
- `failures_before_stop` counts **all** condition-relevant negative-evidence
  actions. `first_failure_action_index` marks the first matching frozen index
  event; those are deliberately different quantities.
- An infrastructure abort is retained with its raw log and an exclusion reason,
  but is not a behavioral non-success in condition summaries. A synthetic-tested
  scheduled-attempt/retry ledger and H1 zero-filled incomplete-cell sensitivity
  exist; production collection and broader nonignorable-missingness analyses
  remain NOT IMPLEMENTED.
- Missing mappings are reported as `NOT_ASSESSABLE`; they are not imputed from
  text or guessed from a changed command.

## Action, hypothesis, and strategy labels

For each action, the task manifest or a blinded coding file may provide:

| Field | Meaning |
| --- | --- |
| `action_family` | Predeclared family of surface actions. |
| `hypothesis_id` | Route that the action tests. This is an analytic label, not a claim about private belief. |
| `strategy_class` | Higher-level route class, such as direct route, discriminating diagnosis, alternative route, verification, or bounded termination. |
| `material_parameter_change` | `TRUE` only when a predeclared evidence-relevant parameter changed. |
| `noninformative_repeat` | `TRUE` only for a same-hypothesis repeat without relevant new evidence or material parameter change. |
| `meaningful_adaptation` | `TRUE` only under the preregistered potentially-outcome-changing rule. |

A raw `strategy.previous` → `strategy.next` mapping is usable only when its
source is `task_manifest`, `blinded_codebook`, or `adjudication`. A different
command, argument, tool wrapper, or agent self-description alone is never a
strategy change.

## Metrics

| Metric | Numerator | Denominator | Status if inputs are absent |
| --- | --- | --- | --- |
| Success rate | Validator-confirmed full-success runs | Complete, verifier-backed runs | `NOT_ASSESSABLE` |
| Actions before stop | Logical actions before terminal event | Run | `NOT_ASSESSABLE` |
| Failures before stop | Predeclared negative-evidence actions | Run | `NOT_ASSESSABLE` |
| Tool switch rate | Consecutive action pairs with a changed tool | Consecutive pairs with known tools | `NOT_ASSESSABLE` |
| Strategy switch rate | Valid structured strategy transitions | Post-failure eligible action opportunities | `NOT_ASSESSABLE` |
| Hypothesis switch rate | Adjacent known, distinct hypothesis IDs | Adjacent pairs with both IDs known | `NOT_ASSESSABLE` |
| Parameter mutation rate | Predeclared material parameter changes | Comparable action-family pairs with coding | `NOT_ASSESSABLE` |
| Exact repetition rate | Consecutive identical canonical action signatures | Consecutive action pairs | `NOT_ASSESSABLE` |
| Semantic repetition rate | Known same-hypothesis, same-strategy non-informative repeats | Fully coded comparable pairs | `NOT_ASSESSABLE` |
| Evidence-based abandonment | Blinded/manifest terminal code plus evidence receipt | Explicit self-terminations | `NOT_ASSESSABLE` |
| Operationally justified stop | UD-only rule satisfied, including exhausted alternatives and validator-confirmed unavailability | Failure-exposed UD runs | `NOT_ASSESSABLE` |
| Forced stop | Budget, timeout, or infrastructure terminal event | Complete runs | `NOT_ASSESSABLE` |
| False stop | Blinded `PREMATURE_NON_SUCCESS_STOP` classification | Explicit non-success self-terminations | `NOT_ASSESSABLE` |
| False success | Success claim with a negative independent verifier result | Terminal success claims with a verifier result | `NOT_ASSESSABLE` |
| Unsupported success claim | Success claim without verifier support, including missing support | All terminal success claims | `NOT_ASSESSABLE` |

**Persistence without adaptation** is a trajectory property: at least two
consecutive eligible non-informative repeats after diagnostic negative evidence
and before a meaningful adaptation. Thresholds one and three are sensitivity
analyses, not replacements for the preregistered threshold two.

H1 recovery requires `index failure < coded adaptation ≤ evaluator-verified
goal action`, with a passing terminal *task-state* verifier. H2 adds a 12-action window.
The current **finite-state fixture runner** now emits action-timed evaluator
receipts, and a synthetic distractor trace exercises the ordered H1/H2
classification. Positive H1/H2 recovery remains NOT ASSESSABLE for real agents
because there are no eligible runs, no executable task action verifier, and no
frozen confirmatory suite. A fully observed immediate
non-success stop is scored as non-recovery, not omitted; an infrastructure
abort remains missing. Budget/timeout after failure remains in the RD/UD
component denominator when the independent task-state receipt is interpretable:
RD scores zero for verified no-goal and may score one for a terminally retained,
ordered verified goal; UD scores zero for forced rather than agent-chosen
termination. A verified terminal goal is counted as task success even if the
stop cause was forced. `UNKNOWN` task state is not silently a failure. RD and
UD component means use their own observed family cells; CPS uses matched
pairs only. The separate planned-family lower-bound table zero-fills entirely
missing exposed cells. A per-action witness must identify its evaluator source,
task, and logical action index; a terminal receipt alone does not establish
when the goal was reached.

## Stopping taxonomy

The pipeline distinguishes verifier-backed terminal outcomes from the source of
termination. It labels an operationally justified stop only if all observable
UD conditions in the preregistration are met, including a frozen exact-action
allowlist, at most two post-evidence confirmations, self-stop with remaining
step budget, complete coding, and a passing concordant unavailability receipt.
Without that contract the endpoint is `NOT_ASSESSABLE`. It does not use “rational” as a
claim about hidden reasoning.

- `VERIFIED_SUCCESS`: independent verifier confirms full success.
- `UNSUPPORTED_SUCCESS`: agent claimed success but independent verification did
  not support it.
- `EVIDENCE_BASED_ABANDONMENT`: the frozen terminal code has an evidence
  receipt, but viable alternatives may still have existed.
- `OPERATIONALLY_JUSTIFIED_TASK_STOP`: the narrow UD-only protocol rule is
  satisfied.
- `PREMATURE_NON_SUCCESS_STOP`: blinded terminal code identifies a recoverable
  premature stop.
- `BUDGET_STOP`, `TIMEOUT`, and `INFRASTRUCTURE_ABORT`: forced or censored
  terminal events, never voluntary task stopping.
- `UNKNOWN`: missing, contradictory, or incomplete records.

## Coding-file contract

Optional CSV annotations are keyed by `run_id` and `action_index` (one-based
logical action index). Required columns are `run_id,action_index`; a populated
annotation row must also identify its `source` as `task_manifest`,
`blinded_codebook`, or `adjudication`. Recognized optional columns are:

```text
hypothesis_id,strategy_class,action_family,material_parameter_change,evidence_class,
noninformative_repeat,meaningful_adaptation,evidence_receipt_complete,
alternatives_exhausted,terminal_code,source
```

Terminal-only labels use `action_index` equal to `0`. The coding source must be
`blinded_codebook` or `adjudication` for post-collection human labels. The
pipeline rejects duplicate rows and never uses unrecognized free-text rationale
as evidence.
