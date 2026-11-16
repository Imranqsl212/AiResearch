# Evidence-sensitive repair: excluded feasibility protocol

Version: 2026-11-16. Implementation: `evidence-sensitive-repair-v1`.

This is a separate feasibility study of whether diagnostic feedback helps an agent decide to preserve or revise an authored program. It implements a narrower, testable part of the literature review's proposed direction. It neither revises the historical cohorts nor supplies missing historical observations. The original manuscript and datasets remain separate.

Every plan, run, and analysis is labeled `phase: excluded_feasibility` and `eligible_for_main_analysis: false`. There is no command that promotes these records into main-study data. The current tasks lack independent human review, a held-out repository evaluation, and a power/precision justification for confirmatory inference.

## 1. Scientific scope and hypotheses

The motivating question is: **Does useful feedback help an agent preserve correct behavior without preventing needed repair?**

The following are hypotheses for subsequent live feasibility experiments, not established findings:

1. On initially correct source, making directional diagnostic information available reduces loss of joint security and functionality relative to an uninformative receipt.
2. On initially defective source, useful diagnostic information increases joint recovery. Analyze unsafe-only, denial-only, and mixed defects separately.
3. Preserving the retained source and completing the interaction are distinct outcomes. Apparent preservation can coexist with invalid attempted edits, exhausted budgets, or failure to terminate.
4. The direction of any damage matters: admitting prohibited requests and denying required requests can respond differently to misleading feedback.

No hypothesis is confirmed by a scripted demo. A future claim that repair effectiveness is preserved would need a named comparator, a justified noninferiority margin, and adequate precision. A nonsignificant difference would not establish noninferiority.

Wrong feedback, test-oracle defects, unnecessary repair, selective abstention, and cost-sensitive verification have substantial prior art. The present implementation is a protocol rehearsal, not a claim to have invented those concepts. The review's nearest-neighbor comparisons remain relevant, including [AMV-Guard](https://arxiv.org/abs/2610.31446) for agent verification and [Qi et al.](https://people.csail.mit.edu/rinard/paper/issta15.pdf) for test-adequate but incorrect repairs.

## 2. Task and candidate boundaries

The benchmark currently supplies four authored families:

| Family | Specified behavior | Scope boundary |
|---|---|---|
| `authorization` | Authentication plus role or ownership | An authored request predicate |
| `csrf` | Authentication, method, origin, and token policy | Not a general browser/web CSRF defense |
| `key_rotation` | Supplied signature validity, expiry, and permitted key | Does not implement cryptography |
| `path_boundary` | Exact raw-path and method allowlist | No filesystem, normalization, or symlink semantics |

Agents submit actual source of this restricted form:

```python
def allow(request):
    return request['authenticated'] and request['role'] == 'admin'
```


This example illustrates syntax, not a universal correct repair. The interpreter accepts a single function with one return expression, known request-field access, bounded scalar literals, Boolean operations, comparisons, and membership in literal lists or tuples. It rejects calls, attributes, imports, assignments, loops, comprehensions, and other Python constructs. Candidate source is parsed, validated, and interpreted by the bounded evaluator; it is not executed with host Python `exec` or `eval`.

The evaluation uses individually authored finite request labels. These cases are not exhaustive over all possible inputs or all allowed source expressions. A pass means the candidate satisfies the evaluated cases, not that it is secure in general. Task names do not establish independent mechanism diversity.

Each family has four initial source controls:

| Stratum | Security cases pass | Functionality cases pass |
|---|---:|---:|
| `CORRECT` | Yes | Yes |
| `UNSAFE_ONLY` | No | Yes |
| `DENIAL_ONLY` | Yes | No |
| `BOTH` | No | No |

All current sources are externally authored common states, labeled `AUTHORED_COMMON_STATE`. They are not agent-generated repairs or selected secure onsets. Correctness is a designed stratum; comparisons between naturally different correct and defective source are not causal effects of correctness itself. Future agent-generated states must remain in a separate source stratum.

## 3. Four feedback arms

A block fixes family, initial stratum, repeat, model identity, public contract, and initial source. Every block reserves all four arms before execution.

| Arm | Initial ordinary verdict | Auxiliary verification |
|---|---|---|
| `TRUTHFUL` | Actual finite-suite joint verdict | Unavailable |
| `FLIPPED` | Opposite of the actual joint verdict | Unavailable |
| `EVIDENCE` | Same flipped verdict | Optional directional diagnostic receipt |
| `NEUTRAL` | Same flipped verdict | Optional uninformative receipt |

Thus the flipped verdict is false FAIL for `CORRECT` and false PASS for the three defective strata. Only the initial verdict is perturbed. Later ordinary attempt checks report the finite evaluator's actual verdict. Persistent corruption is not implemented in this comparison.

`EVIDENCE` and `NEUTRAL` have byte-identical initial visible messages and the same optional `verify_candidate` interface and decision cost. The assigned response type is hidden before the receipt. Diagnostic receipts return security and functionality PASS/FAIL for the current source; neutral receipts return UNAVAILABLE for those fields. Both bind the receipt to the candidate's source hash.

Receipts are padded to **640 UTF-8 bytes**. This matches serialized byte length, not model token count, semantic content, or cognitive difficulty. Token equality has not been established.

The auxiliary tool uses the **same underlying finite suite** as the ordinary evaluator. It is an alternative disclosure channel, not an independent semantic oracle or a checker with independently validated failure modes. This study cannot establish the benefit of independent verification.

The primary contrast is `EVIDENCE − NEUTRAL`, including all assigned branches. Because assignment does not change the visible initial offer, it cannot directly change the initial request decision before the receipt in an otherwise identical trajectory. Different seed slots can nevertheless produce different observed requests. Later verification requests can respond to previously disclosed evidence. Do not analyze only agents that requested verification and call that a randomized effect.

`FLIPPED − TRUTHFUL` compares the initial verdict without the auxiliary tool. Comparing `EVIDENCE` to `FLIPPED` also changes tool availability and the visible interface; it is not a pure diagnostic-content contrast.

## 4. Allocation, actions, and stopping

A plan contains one exact model name and full digest. It reserves four distinct seed slots per block, assigns arms through a reproducible, domain-separated SHA-256 ordering, and uses a separate ordering for dispatch. The seed, model identity, task selection, configuration, sources, and complete branch schedule are fixed before model-generating requests.

These are distinct seeds assigned to arms, not identical random streams reused across every arm. Repeats add within-family variation; they do not create new task families. The present analysis performs no randomization test or population inference.

Every arm can terminate immediately, including after PASS. PASS does not automatically end the run. Inspection, attempted replacement, auxiliary verification, invalid actions, and termination consume the same decision budget. The default cap is three actions. A valid attempted replacement becomes the retained candidate. An invalid source or invalid action preserves the preceding valid source.

Operational completion requires explicit termination without an unresolved invalid action or attempted replacement. Exhausting the cap is not operational completion, even when the retained source passes every case. A valid later attempt can resolve a preceding invalid attempt. Operational completion does not require correct code; an agent can explicitly finish with a defective retained candidate.

A failed transport or invalid provider envelope invalidates that branch. Invalid model action content is recorded as behavior. Failed reserved branches are not replaced with successful reruns.

## 5. Outcomes and denominators

For the evaluated cases:

- **Unsafe acceptance rate** is the fraction of prohibited cases the candidate allows.
- **False denial rate** is the fraction of required cases the candidate denies.
- **Security pass** requires zero unsafe acceptances.
- **Functionality pass** requires zero false denials.
- **Joint pass** requires both.

The rates refer to these finite case sets. They are not deployment-wide probabilities.

The primary outcome is terminal **joint loss** for the `CORRECT` stratum and terminal **joint recovery** for each defective stratum. The endpoint is the retained candidate, including rollback to the initial source when no valid replacement is made. Report operational completion alongside it.

The analysis also reports directional passes/rates, any assessed attempted security or functionality failure after the initial state, a temporary joint failure followed by a passing retained endpoint, invalid attempts, verification uptake, and action counts. The report calls these fields `post_onset`; that name does not make the authored starting states agent-generated onsets. Invalid source has unknown behavioral properties; it is not automatically an unauthorized-acceptance event. Unassessed attempts do not establish the absence of temporary damage.

For invalidated or unstarted branches, final outcomes are missing. Recorded action prefixes remain visible as prefixes, not complete trajectories or zero failures.

## 6. Descriptive analysis and missingness bounds

`analysis.evidence_sensitive.summarize(summary)` is a pure descriptive function. It checks phase, schema, execution kind, initial-state consistency, matching initial source hashes, and all four scheduled arms per block. Artifact authenticity is not established by that function; the CLI first invokes the runner's verified replay.

For one source stratum and one initial-state stratum, define a complete pair difference:

```text
d_i = outcome(EVIDENCE_i) − outcome(NEUTRAL_i)
D_f = mean of complete d_i within family f
reported complete-pair description = mean of available D_f
```


Negative joint-loss differences favor evidence on correct states. Positive joint-recovery differences favor evidence on defective states. Every family's result and pair count remains visible. The report separates all three defective strata; it does not pool them into a single repair effect or combine them with correct-state preservation.

Complete-pair means can be selected by missingness. The report therefore also bounds every scheduled pair. A missing bounded outcome can be anywhere in [0, 1]. For example, if evidence loss is known to be zero and neutral loss is missing, the difference lies in [-1, 0]. Average these bounds over every scheduled pair within a family, then equally across **all scheduled families**, including a wholly missing family.

These are worst/best missing-outcome bounds, **not confidence intervals**. They do not address finite-suite mismeasurement, unrepresented tasks, model drift, or source-selection bias. Unbounded action counts have descriptive observed means without fabricated [0, 1] bounds.

The report contains no p-values, confidence intervals, noninferiority decisions, or main-study release claims. Historical datasets are not inputs.

## 7. Reproduce a scripted rehearsal

Run commands from the repository root. Choose new output names: plan and run artifacts refuse overwrite or implicit resume.

```bash
python3 -m experiments.evidence_sensitive demo \
  --output /tmp/evidence-sensitive-demo-20261116

python3 -m experiments.evidence_sensitive verify \
  /tmp/evidence-sensitive-demo-20261116

python3 -m analysis.evidence_sensitive \
  --run-directory /tmp/evidence-sensitive-demo-20261116 \
  --output /tmp/evidence-sensitive-demo-20261116-analysis.json
```


The demo transport follows a fixed inspect/verify-then-terminate script. It does not call a language model or attempt useful repairs. Its `execution_kind` is `SCRIPTED_HARNESS_CHECK`. A default complete plan contains 4 families × 4 strata × 1 repeat × 4 arms = **64 branches**. Those counts describe software coverage, not sample-size adequacy.

Analysis output must be outside the run directory; adding a file to a sealed run changes its archive inventory. The analysis CLI rejects an output within that directory, including through a symlinked parent, and creates output exclusively rather than overwriting an existing report. Omitting `--output` writes JSON to stdout.

## 8. Plan and run a live feasibility experiment

At the 2026-11-16 implementation checkpoint, the local model inventory inspected for this task contained no installed weights. No live-model findings are reported here. Once an installed model and its exact digest are available, replace the placeholders below and freeze a new plan:

```bash
python3 -m experiments.evidence_sensitive plan \
  --output /tmp/evidence-sensitive-live-plan-20261116.json \
  --model YOUR_INSTALLED_MODEL_NAME \
  --digest YOUR_FULL_MODEL_SHA256_DIGEST \
  --families authorization csrf key_rotation path_boundary \
  --strata CORRECT UNSAFE_ONLY DENIAL_ONLY BOTH \
  --repeats 1 \
  --seed 20261116 \
  --decision-cap 3 \
  --num-predict 512 \
  --temperature 0.3 \
  --timeout 60

python3 -m experiments.evidence_sensitive run \
  --plan /tmp/evidence-sensitive-live-plan-20261116.json \
  --output /tmp/evidence-sensitive-live-run-20261116 \
  --base-url http://127.0.0.1:11434

python3 -m analysis.evidence_sensitive \
  --run-directory /tmp/evidence-sensitive-live-run-20261116 \
  --output /tmp/evidence-sensitive-live-analysis-20261116.json
```


The model name and digest placeholders intentionally fail validation until replaced. The runner checks model identity before requests. A live run is labeled `LIVE_MODEL` but remains excluded feasibility data. The example repeats/budget are configuration defaults, not a power calculation or a scientific recommendation.

## 9. Archive verification and interruption accounting

The runner stores the frozen plan, source inventory and source copies, exact request and response bytes, model identities, action observations, endpoint records, a replayed summary, and an archive index. Requests are persisted before model-generating calls.

`verify_run` replays the archived interaction, reevaluates attempted source, checks feedback and branch allocation, and compares the complete file inventory. It requires the current relevant implementation to match the archived source hashes. After code changes, use the corresponding frozen source in an isolated checkout to reproduce an old run. Hash consistency is internal integrity evidence, not external authentication or proof of sound task semantics.

The standard analysis CLI requires a sealed run. For interrupted-run accounting only:

```bash
python3 -m experiments.evidence_sensitive verify \
  /path/to/interrupted-run --allow-incomplete
```


The Python API can pass `verify_run(path, allow_incomplete=True)` to `summarize` for descriptive crash accounting. Retain all scheduled branches and missing-outcome bounds, label the unsealed status when reporting, and do not create an apparent completed archive by deleting failed branches.

## 10. Implementation checks and next scientific work

The analysis suite includes real-run integration checks for rejected source with valid rollback, transport failure with missing-outcome bounds, matching scheduled arms, unequal family repetition counts, mixed error directions, source-stratum separation, and output preservation:

```bash
python3 -m unittest tests.test_evidence_sensitive_analysis
```


The saved engineering rehearsal is [the v2 run archive](../experiments/runs/evidence_sensitive_harness_20261116_v2/) and [its analysis report](../analysis/evidence_sensitive_harness_20261116_v2.json). Replay verified all 64 scheduled branches as completed, across 16 blocks: four families × four initial strata × one repeat, each with four arms. Both artifacts identify this as `SCRIPTED_HARNESS_CHECK`, with main-analysis eligibility false. These records establish a completed software rehearsal, not a measured live-model response to diagnostic feedback.

At the implementation checkpoint, all **52 evidence-sensitive tests** passed, including **16 analysis tests**. Four historical read-only checks also passed. The original manuscript's SHA-256 remained `58b71372f2742392f7e7748b45bee7053db6b124b6852090555fc19fc2348196`.

The earlier [engineering snapshot](../experiments/runs/evidence_sensitive_harness_20261116/) is retained. A later runner correction changed the current source hashes, so the earlier snapshot must be replayed using its own `source_archive` in an isolated checkout. That replay was checked successfully. The source-drift guard is intentional; do not edit its archive to make it match newer code.

Before a substantive empirical paper, add independently reviewed task semantics, meaningful real-code transfer tasks, defensible family diversity, live-model feasibility estimates, frozen analysis decisions, and precision-based sampling plans. An independent-checker study additionally needs evaluators with deliberately examined shared and distinct failure modes. A cost study needs measured token/latency/currency costs rather than assuming equal byte padding establishes equal resource cost.

