# Which Repairs Can We Credit to the Checker?

**Authors:** Imran Zakirov, Iosifova Nuriya, Kramich Anna

## Abstract

Two groups of coding-agent runs each finished with 15 of 16 programs passing. In one group, an agent undid a successful repair. In the other, it damaged a working program and kept the edit. We traced these outcomes in a preliminary experiment on python-dateutil and CPython that varied when two models could see a diagnostic. Their first implementation choices matched in all 16 pairs. In a follow-up, we gave each of 16 CPython histories one more decision. One probe exposed the observed sorting error and the other produced the same output for faulty and correct code. Under each probe the models recovered all four faulty states and preserved all twelve working states. In a separate historical cohort of 14 paired runs under a known three-decision limit, even the direction of the difference in failing programs changed between decisions two and three. Recording when the program became correct, what the observation could distinguish, and which action followed can rule out explanations that a terminal score leaves open. These two pilots did not include a branch withholding the new post-edit output.

## Introduction

Both versions of our experiment finished with fifteen correct programs out of sixteen. To find the difference, we had to go back one edit. In one run, a CPython pretty-printer initially attached values to the wrong keys. The agent fixed it, then restored the faulty implementation. In another, the printer began in working order. The agent changed how the integer keys were sorted and left the change in place. A maintainer reading the first history would ask why a successful fix was lost. Reading the second, they would ask why a working program was edited at all.

A third question arises when a repair holds. Suppose a pretty-printer sorts integer keys as strings. On keys 2 and 10 it prints 10 first, visibly violating numeric order. On keys 1 and 2 the very same implementation prints the expected order. If an agent fixes the code after seeing either output, what can we credit to seeing the error? We examine this question at the level of a decision. For each choice we track the implementation before and after, the observation available when the model chose, and the reference checks that judged the result.

## How to compare a repair with a decision to leave code alone

The first pilot used two historical test corrections. In python-dateutil, a test compared timestamps during the repeated hour at the end of daylight-saving time. In CPython, a test relied on a particular order when displaying a dictionary. We paired a working implementation with a deliberately defective version for each case. Both versions triggered the legacy assertion. An additional observation showed the parsed local time and UTC offset, or the printed keys and values of another dictionary. Six held-out inputs per project determined whether each selected implementation behaved correctly. These pilots measure functionality on those inputs. [dateutil test correction](https://github.com/dateutil/dateutil/pull/1581) · [CPython test correction](https://github.com/python/cpython/commit/0fd1062a7639f2a155fd6d04eb9cebbd4e5118df)

GPT-6.2 Astra and GPT-6 Luna each had two opportunities to keep an implementation or choose from a small set of source edits. We matched runs by model, project, initial correctness and repetition. One member of each pair saw the diagnostic from the starting program before the first choice. The other saw that observation after the first choice. Both received the same observation by the second choice. Two repetitions yielded 16 pairs, 32 episodes and 64 decisions. Repair is the fraction of defective starts that end with passing code. Preservation is the fraction of working starts that still pass, including cases where an agent selected a different working implementation.

## Two ways to finish at fifteen out of sixteen

**Table 1. Functional correctness by diagnostic timing and starting state.** Each condition contained eight defective and eight working starts.

| Outcome by starting state | Diagnostic before first choice | Diagnostic after first choice |
| --- | --- | --- |
| Defective starts passing after the first choice | 8/8 | 8/8 |
| Working starts still passing after the first choice | 6/8 | 6/8 |
| Defective starts passing after the second choice | 7/8 | 8/8 |
| Working starts still passing after the second choice | 8/8 | 7/8 |
| All starts passing after the second choice | 15/16 | 15/16 |

Every matched pair selected the same implementation on the first choice. Both models fixed the offset-sign error in dateutil and kept its working parser. On CPython, both models edited every working start. Astra chose a working alternative in all four instances. Luna chose string sorting in all four, putting 12 before 2. Counting edits alone would classify these eight decisions together. The held-out checks separated four harmless rewrites from four changes that broke numeric ordering.

The two final failures came from Luna. With the early diagnostic, one repaired formatter reverted to pairing sorted keys with values in insertion order. With the late diagnostic, one initially working formatter retained the incorrect sorting edit. Each second choice ran in a fresh session. The second-choice prompts were byte-identical within all 16 pairs, including these two. The divergent answers document variation between calls to the model. The recorded prompts provide no basis for attributing either final error to the timing of the diagnostic.

The tie also depended on how we scored the sample. The early group preserved every working start and finished one repair short. The late group repaired every defective start and finished one preservation short. An aggregate that weights the recorded repair and preservation rates equally gives the observed tie. Giving either outcome more weight would favor the group that succeeded on all eight trials for that outcome. This arithmetic describes the sensitivity of this score to a scoring choice. The pilot is too small to guide a choice between timing policies. [Timing-pilot report and decision records](https://github.com/Imranqsl212/AiResearch/blob/4d293416957f01da7a83e2c099724fd54c0ffe78/analysis/checker_timing_20261126/comparison.md)

## Was the bug visible when the agent fixed it?

We took all sixteen CPython histories immediately after the first choice. Four contained Luna's string-sorting edit and twelve contained working code. For each history, we gave its original model two separate continuations. Each allowed one choice and displayed an actual run of the current formatter. The keys were 1 and 2 in one continuation, 2 and 10 in the other. We inserted the larger key first and used the same two distinct values in both dictionaries. Ten held-out checks assessed order and key–value bindings.

**Table 2. One further decision from the same CPython edit.** The four faulty states shared a single ordering defect.

| Keys in the displayed run | Order printed by the faulty code | Faulty states repaired | Working states preserved |
| --- | --- | --- | --- |
| 1 and 2 | 1 then 2 | 4/4 | 12/12 |
| 2 and 10 | 10 then 2 | 4/4 | 12/12 |

All four faulty states recovered even when the faulty formatter produced exactly the output a correct implementation would have produced. In those four decisions the agent could not have seen an ordering discrepancy in the displayed output. It could still inspect the source, infer the rule from the task, or use the presence of a check as a cue to reconsider the edit. Both continuations included an observation and a further decision. Their equal success leaves the contribution of those common features unresolved. The models also changed working implementations four times with the first probe and six times with the second. All of the replacements passed. [CPython follow-up and decision records](https://github.com/Imranqsl212/AiResearch/blob/4d293416957f01da7a83e2c099724fd54c0ffe78/analysis/pprint_postedit_20261127/comparison.md)

Temporal order offers a second way to examine credit. In a simpler task, eleven Codex aliases at two reasoning-effort settings received correct and defective lookup tables for doubling integers. All 88 defective starts became correct on the first decision. All 41 requests for a check occurred after the table was correct. Whatever those subsequent observations contributed to stopping or preserving the answer, they arrived too late to produce the first repair. [Sequential effort comparison](https://github.com/Imranqsl212/AiResearch/blob/4d293416957f01da7a83e2c099724fd54c0ffe78/analysis/c5_codex_effort_20261124/comparison.md)

## Which decision was scored?

A historical cohort lets us examine the same measurement problem over a longer trajectory. Qwen3 4B reached a reference-correct candidate on fourteen selected occasions across ten authored task families. We followed two continuations from each occasion. One received truthful feedback and the other received persistent false failures. Both knew the three-decision limit. The 28 continuations contained 78 recorded decisions. After decisions one, two and three, respectively, the counts of branches holding failing code were 4, 8 and 5 under truthful feedback and 1, 6 and 7 under false failures.

Each group recorded eight transitions into failure. At its last decision, each of the six failing branches under false feedback inspected its current candidate. Inspection returned the same candidate with a generic message. Of the eight failing branches under truthful feedback, five submitted again and three restored an implementation that had previously passed. These groups had already diverged before the last decision. The histories establish who submitted, which candidate returned, and whether it passed. A trial that announces two decisions from the outset could produce different first choices. [Historical counts and analysis](https://github.com/Imranqsl212/AiResearch/blob/4d293416957f01da7a83e2c099724fd54c0ffe78/analysis/c5_budget_prefix_audit_20261124/audit.json)

## Relation to previous work

Self-debugging can improve code generation through execution and explanation. Olausson and colleagues found that the gains from repair depended on the task, the computational cost and the model that supplied feedback. COBALT evaluated robustness by perturbing execution feedback during multi-turn coding. These studies motivate a narrower attribution question for an individual run. Was the faulty behavior visible in the observation, and was there time for that observation to influence the repair? [Chen et al., ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/2460396f2d0d421885997dd1612ac56b-Abstract-Conference.html) · [Olausson et al., ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/9ddc141bdbf9d1db510cefff56c586ad-Abstract-Conference.html) · [COBALT](https://arxiv.org/abs/2602.03806)

FixedBench documented unnecessary edits on issues already resolved. Gao and colleagues compared continuations from identical programs under current and stale traces and showed that a policy could protect working starts while sacrificing repair of faulty ones. Our two conditional outcomes follow the same distinction. The CPython comparison varies a different property of feedback. Both probes execute current code, but only one separates the faulty ordering from the correct one. [FixedBench, COLM 2026](https://proceedings.colm.cc/paper_files/paper/2026/hash/b328c5bd9ff8e3a5e1be74baf4a7a456-Abstract-Conference.html) · [Gao et al.](https://arxiv.org/abs/2607.24604v3)

Kim measured the value of a concrete failure directly. Replacing a bare failure status with the first reported failure increased repair by about thirteen percentage points across four revision prompts. The CPython probe addresses a complementary question. When a genuine execution happens to agree with the correct output even on faulty code, success can follow a display that contains no counterexample. The two results concern different information supplied to an agent. [Kim, 2026](https://doi.org/10.3390/ai7100392)

## What would justify crediting the diagnostic?

The repository pilots used two selected tasks, constructed defects and a finite menu of edits. Independent human review of the cases was pending at collection. We selected the keys 2 and 10 after observing the sorting error. Four faulty histories therefore represent repeated opportunities to repair one defect with one model. The historical policy study used a different model, task set and interface. Pooling decisions across these studies would obscure the units on which their observations depend.

A prospective test could hold the source, prior history and one remaining decision fixed, then assign each continuation to receive a revealing output, a genuine output that conceals the fault, or no output. It would select probes before model collection and repeat across independently reviewed defects and working controls. The first comparison would estimate the incremental value of exposing the discrepancy for the chosen pair of probes. Comparing each output with withholding it would estimate the value of showing that diagnostic under those conditions. A separate planned experiment varies the announced and enforced decision limit at a common verified repair. That design addresses a different uncertainty raised by the historical reversal. [Verdict and decision-budget protocol](https://github.com/Imranqsl212/AiResearch/blob/4d293416957f01da7a83e2c099724fd54c0ffe78/docs/C5_BUDGET_STATISTICAL_PROTOCOL_20261124.md)

In the CPython pilot an agent sorted integer keys as strings, saw a perfectly ordered pair, and corrected the code on its next choice. We can establish that the repair occurred and that the displayed pair gave no visible sign of the error. What would have happened had the agent simply been offered another turn? The answer requires a branch in which we let it do exactly that.

## Data and authorship

The public records linked above give the pilot assignments, implementation scores and paired decisions. Codex assisted with analysis and drafting. This alternative draft covers the exploratory pilots completed through 27 November 2026. The subsequent display and reference-example experiments are reported in the primary manuscript. Author approval is pending.
