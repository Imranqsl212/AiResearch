# When a Checker Rejects a Correct Repair

**Authors:** Imran Zakirov, Iosifova Nuriya, Kramich Anna

## Abstract

A coding agent has already produced a repair that satisfies the task. Its checker says it failed. Does the agent keep working, and what happens to the repair? We reconstructed matched continuations from an exploratory study of a local coding model and finite policy tasks. Each pair started from the same verified candidate. In 14 selected pairs with persistent feedback, three truthful-pass branches stopped before the decision limit. No false-failure branch stopped early. The false-failure branches nevertheless submitted fewer additional candidates (17 versus 28). Their first action was usually to inspect the task (12 of 14 pairs, versus zero). The conclusion about damage depended on when we looked. More false-failure branches ended with a failing candidate (7 versus 5), but fewer ever submitted a failing candidate (7 versus 8). In two later incomplete waves on request authorization, every observed terminal regression denied a legitimate request. A simple regression count would conceal which party bore the cost. We describe a prospective comparison that changes one verdict after a verified repair, records the controller event that honored a stop, and measures prohibited acceptance and legitimate denial separately. The archived observations motivate this comparison. They do not estimate a population effect of scanner errors on coding agents.

## Introduction

A failed security check usually invites another edit. That advice is reasonable when the code is defective. When the current repair already satisfies its specification, another edit introduces an opportunity to lose a working solution. An edit count misses both an agent that exhausts its budget inspecting a correct repair and one that damages it in a single attempt.

Our starting point was an audit of 40 local repair runs. In nine of twenty runs under a hidden acceptance veto, the final candidate passed the implemented family checks and was still rejected. The runner also issued 38 self-termination labels after exhausting its protocol reminders. These observations identified two distinct measurement problems. The displayed verdict can disagree with the reference, and the runtime can end an episode independently of an agent’s request. We therefore ask one question: after a verified repair, how does false feedback change an agent’s decision to stop and the state of the repair when execution ends?

ImpossibleBench deliberately introduces contradictions between specifications and tests and measures solutions that pass despite the contradiction. COBALT studies coding under misleading test feedback. In our paired design the agent has already supplied an independently checked solution before feedback diverges. The object of comparison is its next decision and the fate of this particular candidate. CWEval and BaxBench both evaluate functionality alongside security. That distinction also belongs inside a repair trajectory: replacing a policy with one that denies every request may protect an access boundary while breaking legitimate use. [ImpossibleBench, ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/ca688eb14e29701a11bdba6633186328-Abstract-Conference.html) · [COBALT](https://arxiv.org/abs/2602.03806) · [CWEval](https://ieeexplore.ieee.org/abstract/document/11028476) · [BaxBench, ICML 2025](https://proceedings.mlr.press/v267/vero25a.html)

## Observations and estimands

The historical model was Qwen3 4B. In the C5 experiments it proposed finite policies on authored tasks. A secure onset is the first candidate judged correct on the bounded specification. Each continuation starts with this candidate and the same prior interaction. The archived protocols differ in how often a false verdict was delivered, which families reached onset and whether collection completed. We report each protocol separately. A pair is one onset with two arms. Multiple steps, repeats of the same trace and different prompts for one family do not provide independent families.

An early stop requires a task-specific terminal action honored by the controller before the final permitted decision. In the prospective protocol this can be an explicit terminate action or an accepted structured terminal claim. The action types are recorded separately. A voluntary stop on the last decision consumes the full budget. For terminal regression, the candidate retained when the branch ends fails the bounded reference. A branch that keeps its onset candidate retains that verified candidate. Temporary regression records any post-onset failing submission. We distinguish a false acceptance of prohibited work from a false denial of legitimate work whenever per-case observations permit. A combined finite-oracle failure alone cannot make that distinction.

## Results

**Table 1. Selected persistent-verdict cohort.** Fourteen paired onsets from ten families. The denominators for the first four rows are 14 arms per condition. The last row counts submissions.

| Observable outcome | Truthful PASS | False FAIL |
| --- | --- | --- |
| Early voluntary stop | 3 | 0 |
| First action was inspection | 0 | 12 |
| Any post-onset regression | 8 | 7 |
| Terminal regression | 5 | 7 |
| Additional submissions | 28 | 17 |

The branches receiving false failures used all three decisions in every pair, yet they generated eleven fewer candidates overall. Inspection consumed part of the budget. For terminal regression, four pairs failed in both arms, three only after false failure, one only after truthful pass and six in neither. The paired terminal difference was +2/14. Giving each family equal weight produced +15 percentage points. For any temporary regression the corresponding family-weighted difference was −10 points. A terminal code snapshot and a history of attempted edits answer different questions about damage. Only two of these fourteen historical pairs exposed directly comparable Boolean outcomes for allowed and prohibited cases. Both began with correct decisions on every case. At termination, the truthful branches accepted one of seven prohibited cases and the false-failure branches accepted five of seven. Both conditions still served all three required cases. The other twelve pairs have no comparable decomposition under this rule.

**Table 2. One-shot follow-ups.** Each pair received a single truthful or false initial verdict, then followed the same continuation protocol. These small waves were scheduled sequentially.

| Cohort | Verified pairs / precursors | Early stop, PASS / FAIL | Terminal regression, PASS / FAIL |
| --- | --- | --- | --- |
| First wave | 3 / 4 | 3 / 2 | 0 / 1 |
| Subsequent families | 2 / 4 | 1 / 1 | 1 / 1 |

An authorization trajectory in the first wave repeated an earlier deterministic path. In the second wave, both arms of a signature-policy task produced the same failing final candidate. In two further temperature-0.3 waves, each with four completed authorization pairs, the terminal counts were 0 versus 3 and 1 versus 3. All seven regressing arms denied a legitimate request. In a separate six-pair follow-up, a key-rotation pair failed in both arms but in opposite ways: the truthful arm denied a current key and the false arm accepted a retired key. A false verdict can precede either type of error. Neither the rate nor its direction can be transported to other models from these observations.

The secondary comparison, C4 versus C3, changed the explanation of an unsatisfiable finite task. A truthful explanation described the missing information; its control provided a generic failure. Neither arm stopped early in any of six matched blocks across two families. Every arm made two submissions. Two C4 episodes stopped voluntarily on the final decision. Counting any voluntary stop as early stopping would change the reported result.

## What the instrument can detect

The prospective checker accepts a typed candidate from a finite language and evaluates it in a separate process. The agent cannot supply an evaluator program through that interface. The private receipt distinguishes the example-level raw check, the finite reference result and the displayed verdict. The source record and evaluated candidate have separate identities, allowing later analysis to check the actual input at each step. This separation is specific to the finite study. The historical free-form Python evaluator remains a different instrument.

**Table 3. Calibration before model collection.** Each row below covers every enumerated policy in one v7 family under truthful checking. “Caught” counts invalid policies rejected by the example test. The reference column gives erroneous rejections by the normal acceptance gate. Each of these eight families has one correct policy in the enumerated language.

| Family | Invalid policies caught by raw test | Correct policies rejected by normal gate |
| --- | --- | --- |
| csrf origin | 1/3 | 0/1 |
| deserialization allowlist | 1/2 | 0/1 |
| environment injection | 1/2 | 0/1 |
| kdf salt | 2/3 | 0/1 |
| key rotation | 1/2 | 0/1 |
| nonce uniqueness | 1/2 | 0/1 |
| signature algorithm | 1/2 | 0/1 |
| tls hostname | 1/2 | 0/1 |

Across 20 registered families and 28 family-version combinations, 390 designed candidates were checked in each condition. The normal gate caught all 354 bounded-property violations and rejected none of 36 valid references. The raw example test alone caught 285/354. When the C5 rejection policy was applied, it rejected all 36 valid references despite their raw passes. These are counts over enumerated policies, including over-restrictive policies. They measure coverage of this finite language and the injected feedback mechanism. They do not estimate how often a real scanner raises a false alarm.

We also adapted two published Python task specifications from CWEval. One requires file contents and owner-only permissions. The other specifies password derivation with a per-password salt. For each task, we generated a benign reference observation and independently corrupted the functional observation, the security-related observation, or both. The controls recovered all four combinations on both tasks. An additional control produced four distinct but predictable salts. It passed the nonrepetition check. That check detects reuse within the observed sample; it cannot certify unpredictability. These are calibration observations on two deliberately chosen specifications. The upstream test suite and model trajectories from CWEval were not run. [CWEval file specification](https://github.com/Co1lin/CWEval/blob/e9a2a124c8c53679b6d8d27adfd2f6c40e7576d7/benchmark/core/py/cwe_732_2_task.py) · [CWEval password specification](https://github.com/Co1lin/CWEval/blob/e9a2a124c8c53679b6d8d27adfd2f6c40e7576d7/benchmark/core/py/cwe_760_0_task.py)

## Prospective test

The primary endpoint is the change in early voluntary stopping after one false FAIL versus truthful PASS at the same verified onset. Terminal regression and the C4–C3 early-stop contrast are secondary. We will record all scheduled precursors, missing onsets, technical failures and completed forks. The target population for the C5 contrast is the set of eligible onsets under the defined sampling scheme. An agent that never reaches onset contributes important coverage information, but cannot supply a missing experimental pair.

The design calls for four to six model deployments across distinct families. The four-model candidate schedule covers nineteen authored task families, three prompt wordings and five repeats at temperature 0.3. A separate pair receiving the same verdict on both arms measures divergence under identical treatment. Exact provider identifiers, sampling settings, returned identity metadata and the selection policy for onsets must be fixed before collection. Equal weighting across task families and multiplicity control across the named model contrasts are prespecified. A simulation illustrates the cost of family dependence. With 19 task families, 50% onset reach, 5% pair loss and a 30% discordance probability, about 271 complete pairs per model remained. At the first Holm threshold of 0.01, a ten-percentage-point reduction in early stopping was detected in 57% of simulations with independent paired differences and in 11% with a within-family correlation of 0.2. For a twenty-point reduction the corresponding probabilities were 99.9% and 73%. These are planning assumptions. Even the larger candidate roster may have too little power to detect a modest effect. The early-stop contrast is conditional on the action budget. It cannot estimate the effect of an actual scanner’s real-world false-positive rate.

## Limitations and conclusion

The archival cohorts use one small model, selected secure onsets and a small number of authored families. Some waves stopped after technical failures and one deterministic trajectory recurred. The historical contrasts are descriptive. Public-repository audits of stopping establish what records survive an export but cannot identify the causal effect of feedback. No confirmatory model outcomes or independent human agreement estimates are available. Registry publication, model access and independent semantic review are prerequisites for the prospective claims. Context retrieval, second opinions and false passes are separate interventions for future work.

Two accounts make different predictions in the prospective experiment. If a false failure prompts the agent to reconsider the checker’s evidence, its next action should shift toward inspection, and additional edits may fall even as more branches use their full decision budget. If the agent treats failure as a direct instruction to repair, the first new action should more often be a submission. The 14 historical pairs favor the first description. Their records identify the action taken, while the agent’s reason for taking it remains unknown.

The clearest observation is that false failures changed how these runs spent their remaining decisions. Measuring the damage requires a second question. Which service did the final policy cease to provide, or which prohibited action did it begin to allow? A stopping label and a single security score cannot answer both.

## Data and research contributions

The data supplement contains 78 structured decisions from the 28 persistent-verdict continuations. Source receipts bind the derived records to their archived events. The supplement includes a machine-readable schema, calibration controls, and a separate statistical plan. The historical model observations predate the new plan. Codex assisted with analysis and drafting. Human author approval and an external data deposit are pending.
