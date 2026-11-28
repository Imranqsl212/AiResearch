# When Should a Model Put the Bug Back?

**Authors:** Imran Zakirov, Iosifova Nuriya, Kramich Anna

## Abstract

A published sorting bug discards duplicates. For a caller who needs distinct values, putting it back is the right repair. On four QuixBugs algorithms we held the code and input fixed, changed one required answer and let two hosted models write a patch. They implemented both opposing requirements in 10/16 pairs (Astra 8/8, Luna 2/8). Under the alternative requirement the published tests rejected all 13 correct responses and accepted all three incorrect ones. Removing the rule descriptions left paired success at 5/9 on the repeated blocks, while three gains on the published task offset three losses on its alternative. On eight additional tasks, models followed both opposing values in 8/8 pairs when described as requirements, 8/8 when attributed to an unspecified candidate, and 2/8 when the candidate was named. A Matplotlib regression recurred in one of four fresh decisions from working code. It passed the maintainer's test on a real axis and failed 34/96 other inputs. Crediting feedback for a repair requires knowing which behavior was requested, who supplied the example, and whether the test still detects the fault after the edit.

## Introduction

Take the list [8, −2, 8]. A published sorting bug returns [−2, 8]. The benchmark repair returns [−2, 8, 8]. Now suppose the caller needs each value once. The bug is a working implementation. Starting from the benchmark's patched sorter, satisfying this caller means putting the discarded behavior back. Can a coding agent tell which change to make from a single example, even when that change runs against the benchmark's own correction?

![Figure 1. Four tasks in which the original QuixBugs program and the published fix implement different target conventions. The model saw one of the listed answers for the same input. Each task has two models and two starting programs. The last column counts matched pairs that implemented both assigned contracts in their respective sessions. Knapsack items are written as weight/value.](figures/contract_reversal.png)

A passing test after an edit is evidence about the resulting program. It tells us little about why the agent made that edit. In our CPython pilot, agents fixed a sorting error even after a run that printed the keys in the correct order. On a working dateutil parser, a run that displayed a correct positive UTC offset preceded an edit that broke negative offsets. The mirror image of these cases is a task whose specification admits two answers. Knowing what the current code printed cannot settle what the caller wanted. Reporting the caller's answer can.

We study that distinction by changing one part of a repair decision at a time. On four public algorithm tasks we ask for a patch in both directions, keeping the code and example input fixed. On eight additional authored tasks the value itself can stay fixed while its description changes from a target requirement to an observation about a candidate. We then vary how much the written specification already says and measure how often repeated draws of the same editing prompt disagree. The unit of evidence is the matched comparison on a particular starting program.

## How we distinguish repair from preservation

Each decision begins with a concrete implementation. We grade it and the retained implementation against the same assigned contract on undisplayed inputs. If faulty code passes after the decision, the agent repaired it. If working code continues to pass, the agent preserved its behavior, even if it rewrote the source. We keep these denominators separate. A source can count as a working start under one contract and a defective start under another. Passing a finite test suite is an operational outcome with known limits (Qi et al., 2015).

Each hosted model made one tool-disabled editing decision in a fresh Codex CLI session per follow-up prompt. Most use GPT-6 Luna and GPT-6.2 Astra at low effort. The study of identical values also schedules GPT-6.2 Sol and GPT-6.1 Terra. These are requested configurations. Each follow-up fixed its prompts, assignments and graders locally before its first call. Earlier pilot results informed later designs. The decision records distinguish a usable reply, a failed call and an assignment that was never sent. Repeated histories and finite test inputs are separate from the number of independent projects.

## A benchmark fix can become the bug

We inspected four single-expression defects from QuixBugs (Lin et al., 2017) and identified a second coherent contract for each. The sorting defect removes duplicate pivots recursively and therefore returns the distinct values in order. The maximum-sum defect computes the largest prefix sum when the empty prefix is allowed. The parentheses defect accepts a string that can still be balanced by appending closing parentheses. The knapsack defect enforces a strict capacity bound, with an empty packing always allowed. These alternative contracts change the assigned task. The original benchmark labels retain their meaning under the published requirements. For integer lists, the sorting example corresponds to two operations exposed by NumPy, an ordinary sort and sorted unique values. [NumPy sort](https://numpy.org/doc/stable/reference/generated/numpy.sort.html) · [NumPy unique](https://numpy.org/doc/stable/reference/generated/numpy.unique.html)

We wrote an independent reference for each alternative and checked both starting sources under both contracts. The references disagree on 105 of 121 sorting inputs, 32 of 121 maximum-sum inputs, 19 of 63 parentheses inputs and 117 of 240 knapsack inputs in the original grading domains. On all four domains the benchmark defect implements the alternative, while the published fix implements the upstream contract. The two programs can therefore exchange roles without changing a byte of starting code. An agent that follows the new requirement should sometimes recreate the behavior the benchmark labels buggy.

For each algorithm we showed the same function and described both possible contracts. The model saw the location of one editable expression and could keep it or write a replacement from scratch. Within each matched pair, the prompts differed only in the literal answer from the trusted target installation. A third prompt withheld that answer. We scored each resulting expression under both contracts, and asked whether the model met each of the two opposing requirements in separate sessions starting from the same code. We used all four tasks previously admitted to the free-expression study. The alternative requirements were constructed after inspecting the faulty source and frozen before asking any model to implement them.

The model produced a program meeting each requirement in its respective session in 10/16 complete pairs. With the published target shown, 7/8 faulty starts were repaired and 6/8 working starts preserved. With the alternative target shown, 7/8 faulty starts were repaired and 6/8 working starts preserved. In that last repair count, the starting program was the published correction and the requested behavior was the one the benchmark classifies as buggy. Astra met both contracts in 8/8 pairs and Luna in 2/8. Of the six remaining pairs, three produced the published behavior both times and three produced the alternative both times. The six invariant pairs selected the same parsed expression on both calls. Two preserved the starting behavior twice and four changed it twice. Always keeping the source or always choosing one fixed convention scores zero pairs. A solver with both reference implementations could execute them on the example input and score all sixteen pairs. Models had to supply their own replacement expressions. With the target withheld, 7 choices implemented the upstream behavior, 9 the alternative, and 0 neither. Those counts reflect the wording, names and starting programs as well as any prior familiarity.

**Table 1. Assigned target for the same QuixBugs source. The concealed decision is assessed under both contracts. A free expression can fail both.**

| Target shown | Valid / scheduled | Defective starts repaired | Working starts preserved |
| --- | --- | --- | --- |
| Withheld | 16/16 | 3/16 | 13/16 |
| Upstream behavior | 16/16 | 7/8 | 6/8 |
| Alternative behavior | 16/16 | 7/8 | 6/8 |

We regraded the same programs on 15,962 further task–input pairs disjoint from the original finite domains and displayed inputs. Of 42 reversal assessments that passed their assigned contract originally, 42 continued to pass. The two QuixBugs studies together produced 9 distinct task-specific parsed expressions. Repeated responses can return the same expression.

The benchmark's own default tests give a second perspective. Only one of its thirteen sorting cases distinguishes sorting with multiplicities from sorting distinct values, compared with 105 of our 121 original inputs. Across the four tasks, twelve of the 31 default benchmark cases separate the conventions. We retained the upstream exclusion of one slow knapsack case. Of the 13 choices that implemented the disclosed alternative, 13 failed at least one published test. All three incorrect responses to the alternative instruction passed every default benchmark test for their task. All sixteen decisions received opposite grades from the assigned contract and the original suite. This inversion follows once every returned program implements one of the two conventions and every published suite distinguishes them. The observed result is which behavior the models produced. [Pinned QuixBugs cases](https://github.com/jkoppel/QuixBugs/tree/4257f44b0ff1181dedaedee6a447e133219fcebf/json_testcases)

The choice of inputs therefore changes what even an ideal observer could infer. Suppose the two contracts are equally likely, the observer knows both, and one trusted answer is drawn on a uniformly sampled input. A distinguishing example resolves the contract. An agreeing example leaves a one-half chance of guessing correctly. For sorting, the resulting ceiling is 7/13 (53.8%) when sampling one of the published tests, and 113/121 (93.4%) on our original finite domain. Our prompts deliberately chose a distinguishing input. These ceilings describe the two sampling rules.

To test how much the models relied on the two named conventions, we deleted only the two description lines and repeated the target pairs. The prompts still disclosed that two conventions existed and supplied the same source and required output. Eighteen of 32 scheduled calls were completed. The same five of nine matched blocks implemented both contracts with and without the descriptions. The individual grades moved in opposite directions. Removing the descriptions gained three successes on the published target (6/9 to 9/9) and lost three on the alternative (8/9 to 5/9). All three gains and losses involved the same three Luna starts. In two, the model went from implementing the alternative twice to implementing the published behavior twice. These were fresh calls in successive cohorts, so sampling and time variation remain possible contributors. Even if all seven outstanding alternative responses had succeeded, the omitted condition could reach only 12/16, below the named condition's observed 13/16. In one Luna response the final parentheses check became `depth == 2`. It reproduced the required true answer for the displayed string and failed both contracts on the empty string. One observed example made the intended behavior distinguishable among the two named programs, while leaving many other programs possible.

## What does the same displayed value tell the agent?

On eight new tasks, each with two supplied implementations, we could truthfully display the same value under three descriptions. The captions read “Required output of the target installation”, “Observed output of one of the two candidate implementations”, and “Observed output of the current implementation” or “Observed output of the alternative implementation”. The value printed beside each caption stayed fixed across the comparison. Both candidates were executable. Only the first description identified the caller's requirement. For each description we showed both opposing values in separate fresh sessions. A seventh prompt showed no value. The tasks covered endpoint inclusion, duplicate retention, signed division, moving sums, weekday indexing, unequal-length distance, matrix traversal and empty fields.

For example, on weekday 6 the Monday-first implementation returns 6 and the Sunday-first implementation returns 0. A required answer of 0 identifies the Sunday-first convention. An unspecified candidate printing 0 identifies a behavior available to the agent. Either convention could still be the caller's. For each description we counted blocks where the model selected the program that produced each of the opposing values. For candidate executions this measures alignment with the value. A developer might also infer that the experimenter chose a value for a reason. The named-candidate display additionally identifies which program produced it. The primary paired contrast compares the required and anonymous captions within blocks observed under both.

We obtained 56 usable decisions from 448 scheduled calls. Under the required caption, models followed both opposing values in 8/8 completed pairs. They did so in 8/8 under the anonymous caption and 2/8 with the producing candidate named. Among the 8 blocks available under both required and anonymous captions, 0 tracked both required values alone, 0 tracked both anonymous values alone, 8 tracked both captions, and 0 tracked neither. With no value shown at all, 8/8 usable responses kept the starting implementation.

**Table 2. Behavioral response to the same value with different descriptions. A row counts completed opposing-value pairs for that description. The last two columns count pairs making the same keep or switch action twice.**

| Source of value | Followed both / complete | Always kept | Always switched |
| --- | --- | --- | --- |
| Unspecified candidate | 8/8 | 0 | 0 |
| Named candidate | 2/8 | 6 | 0 |
| Target requirement | 8/8 | 0 | 0 |

Unobserved blocks matter. Counting all 64 scheduled blocks, the net gain in pairs following both values when described as required versus anonymous can range from -56 to 56 under all completions consistent with the ledger. In a secondary check, we subtracted pairs that opposed both values from pairs that followed both. This signed count was +8 for the required caption and +8 for the anonymous caption. A value-insensitive policy making independent draws can occasionally follow both values by chance. It is equally likely to oppose both. On the 8 blocks observed under both the named-candidate and required captions, 6 tracked only under the requirement and 0 only when the source candidate was named. The contrast with the named candidate simultaneously changes the authority of the source and identifies which implementation generated the value. Either cue can influence the choice. In the direct comparison of the two execution captions, 6 of 8 complete blocks tracked both values under the anonymous caption alone and 0 under the named caption alone.

After seeing the first eight blocks, we fixed a fresh 32-call comparison on those same blocks. The control used the original anonymous caption. The second condition added two sentences explaining that both candidate outputs were shown equally often under either possible target, so the displayed value gave no information about which convention was required. The original quota window closed before any of the 32 calls started. Whether disclosing how examples were selected changes model behavior remains open.

## Does the written specification already give the answer?

On the three authored tasks from the earlier reference-example control (Table S3), we held the implementations and input fixed and varied access to the current program's actual output and to the caller's required output. We repeated the comparison after naming the target convention in the specification. The primary contrast adds the caller's answer to the same actual output. Under hidden wording, neither the baseline prompt nor the execution-only prompt distinguishes the two target assignments. We collected each once and graded each decision against both possible contracts. One of those two grades must pass because the menu contains exactly the two alternatives. The two grades from a shared prompt are dependent by design.

Of 168 scheduled decisions, 84 were usable. With the target hidden, execution alone yielded 1/6 repairs and 5/6 preservations. Adding the required output yielded 6/6 and 6/6. On matched comparisons, repair gained 5 and lost 0. Preservation gained 1 and lost 0. Once the rule was named, the same addition gained 0 repairs and lost 0, with 0 gains and 0 losses in preservation. These are responses on three selected task mechanisms. Over all twelve assigned blocks, the net change in repairs from adding the target answer could range from -1 to +11. Over all twelve assigned blocks, the net change in preservations from adding the target answer could range from -5 to +7.

**Table 3. Actual and required output on a fixed input. Each shared hidden call without a disclosed target has two dependent grades. The denominator in each outcome column counts usable target assessments in the indicated starting state.**

| Rule and display | Valid / scheduled calls | Defective starts repaired | Working starts preserved |
| --- | --- | --- | --- |
| Hidden / neither | 6/12 | 0/6 | 6/6 |
| Hidden / actual | 6/12 | 1/6 | 5/6 |
| Hidden / required | 12/24 | 6/6 | 6/6 |
| Hidden / both | 12/24 | 6/6 | 6/6 |
| Explicit / neither | 12/24 | 6/6 | 6/6 |
| Explicit / actual | 12/24 | 6/6 | 6/6 |
| Explicit / required | 12/24 | 6/6 | 6/6 |
| Explicit / both | 12/24 | 6/6 | 6/6 |

## Writing patches for published defects

The earlier forks provided a short menu of implementations. To test whether those choices depended on recognizing the correct option, we next supplied a function with one marked expression. A model could leave it in place or write a replacement. Four Python functions came from QuixBugs, a set of published one-line algorithm challenges (Lin et al., 2017). We used the reported defect and the benchmark correction for sorting, balanced parentheses, maximum subarray sum and knapsack. The upstream files, extracted expressions and independent finite checkers were fixed before collection. Every returned expression in the supported language was graded in a bounded interpreter. Separate runs of the original upstream functions checked the calibration.

Each model encountered all eight starting sources, once per display condition. With no new execution, seven of eight defective starts were repaired. With either a shared or revealing execution all eight were repaired. All three arms preserved all eight working starts. Luna retained the faulty maximum-sum update without a display. A shared example on which both implementations agreed and a revealing example both preceded a successful edit on that start. Across the experiment, the models wrote 23 replacements. Every replacement had the same parsed expression as the corresponding upstream fix. Four independently checked, syntactically different expressions also passed, one per task. This convergence left open a sharper question. Would the model still write the familiar correction when a different behavior was expressly required?

To check whether this result extended beyond algorithm challenges, we took two historical BugsInPy repairs (Widyasari et al., 2020). Matplotlib's interval update had to extend the range of an inverted axis while preserving its direction. In tqdm, an enumeration wrapper had to honor a nonzero start and still forward iteration through the progress bar. The model could retain or replace one marked expression in code extracted from the defect or its fix. We graded both directions on 96 interval cases and 45 enumeration cases, and checked the extracted semantics against isolated runs of the pinned upstream functions.

On the maintenance fixes, the shared display yielded four of four repairs and preserved all four working starts. The test chosen to distinguish the reported defect yielded three of four repairs and three of four preservations. All twelve tqdm decisions passed both components, including the check that a progress wrapper was actually iterated. The three unsuccessful final decisions across the study occurred on Luna's Matplotlib starts. Astra passed in every condition.

**Table 4. Writing one expression at a specified source location. Each fraction counts usable model–task–start decisions in the row. “Revealing” identifies a test that distinguishes the two original sources.**

| Source collection | Display | Defective starts repaired | Working starts preserved |
| --- | --- | --- | --- |
| QuixBugs | No output | 7/8 | 8/8 |
| QuixBugs | Shared output | 8/8 | 8/8 |
| QuixBugs | Revealing output | 8/8 | 8/8 |
| Maintenance fixes | No output | 3/4 | 4/4 |
| Maintenance fixes | Shared output | 4/4 | 4/4 |
| Maintenance fixes | Revealing output | 3/4 | 3/4 |

On Matplotlib the very input that exposed the historical bug concealed the new one (Figure 2). Starting from the working version with the old interval [8, 2], Luna saw that adding [3, 7] correctly retained [8, 2]. Its replacement reproduced that output and kept the direction correct on all 96 checks. It nevertheless failed the interval extent on 34. On the other arm's input, adding [0, 10] should have extended the interval to [10, 0]. The new patch returned [8, 2]. Exactly the reverse held for the historical defect: the contained span exposed its error and the expanding span did not. A probe earns the label “revealing” relative to two particular implementations. An edit can change which probe deserves that label.

![Figure 2. The same two input spans on an inverted Matplotlib axis. The arrow runs from the first endpoint to the second. The historical defect and the new model-written regression pass different probes. Each interval comes from executing the recorded expression in the frozen evaluator.](figures/probe_reversal.png)

The recorded interval expressions permit a stronger check. Every coordinate of the generated regression and the maintainer fix is a nested minimum or maximum of the four input endpoints. Strictly increasing relabelings preserve these operations. With unequal original endpoints, four finite real scalars admit 62 distinct orderings including ties. Testing one representative per ordering therefore settles interval correctness throughout this fragment. The historical defect passed 39 orderings and the new regression passed 44. One additional input separates all three behaviors. Starting at [8, 2] and requesting [0, 7] gives [8, 0] for the correct version, [7, 0] for the historical defect and [8, 2] for the generated regression. This is a property of the recorded expressions and scalar specification.

We then repeated the six Luna prompts from both historical starts four times each, yielding 24/24 usable decisions. With no display, 0/4 faulty starts were repaired and 4/4 working starts preserved. The corresponding counts were 1/4 and 2/4 with the expanding span, and 1/4 and 3/4 with the contained span. Of 4 repeats from working code on the contained span, 1 produced a failure that passed both that probe and the maintainer's regression example but failed the expanding-span probe. The separate mixed-span input detected 13 of 13 held-out failures across the repeat study. All runs concern this one source change. The repeated regression used exactly the same expression as the discovery response. The mixed-span probe accepted all eleven passing results and rejected all thirteen failures, which comprised four distinct erroneous expressions. Their 62-order certificates agreed on all 24 decisions. We selected this probe after the initial discovery and froze it before collecting these repeats.

We also tested the three edits through the public Matplotlib API. We loaded the Python sources from the historical fix with Matplotlib 3.1.2 binary extensions and ran the maintainer's original test on the Agg backend. The test failed on the historical defect and passed on both the maintainer fix and the generated regression. When we set ticks on fresh axes and read back their limits, the historical defect passed 58/96 intervals, the maintainer fix 96/96 and the generated regression 62/96. Each result matched the finite checker. All 96 generated results kept the original axis direction. What broke was how far the axis extended. [Upstream Matplotlib change](https://github.com/matplotlib/matplotlib/commit/407a9fe71a4c0a8ba4914b8f54f21d32d6dd2d74)

## Two equal final scores conceal different failures

Four upstream test corrections in CPython, pandas and python-dateutil changed tests while leaving the relevant implementation intact. We chose two before independent human review. In dateutil, a parser preserved wall time and UTC offset across a daylight-saving transition, but Python’s inter-zone equality rule invalidated an assumption in the legacy assertion. In CPython we examined the order of printed dictionary keys and the values attached to them. In each case a deliberately defective implementation and the historical working implementation triggered the same legacy assertion. [Upstream dateutil correction](https://github.com/dateutil/dateutil/pull/1581) · [PEP 495](https://peps.python.org/pep-0495/#aware-datetime-equality-comparison) · [Upstream CPython correction](https://github.com/python/cpython/commit/0fd1062a7639f2a155fd6d04eb9cebbd4e5118df)

Two models, GPT-6.2 Astra and GPT-6 Luna at low effort, could keep the current implementation or choose from specified source edits. Each episode allowed two decisions. The early arm saw the diagnostic for the starting code before choosing. The late arm received the same diagnostic after choosing. Model, project, initial correctness and repetition defined 16 pairs, hence 32 episodes and 64 decisions. Six held-out inputs per project assessed each candidate. Both arms selected exactly the same first implementation in every pair.

**Table 5. Repair and damage in the preliminary timing pilot.** Each timing condition had eight defective and eight correct starts. A version counted as correct if it passed all six held-out checks for its project.

| Outcome | Diagnostic before first choice | Diagnostic after first choice |
| --- | --- | --- |
| Defective starts repaired at first choice | 8/8 | 8/8 |
| Correct starts damaged at first choice | 2/8 | 2/8 |
| Defective starts correct at final choice | 7/8 | 8/8 |
| Correct starts still damaged at final choice | 0/8 | 1/8 |
| All starts correct at final choice | 15/16 | 15/16 |

On dateutil, every defective parser was repaired and each working one was retained. In CPython, Astra rewrote working formatters while preserving behavior. Luna’s rewrites of the working formatter sorted integers by their text. The two final failures both occurred in Luna runs. In the early arm the agent repaired a defect, then reintroduced it by pairing sorted keys with values in insertion order. In the late arm the agent introduced the text-order bug into a working formatter and kept it. Each second choice came from a fresh session. Second prompts matched byte for byte within all 16 pairs. The two differing final implementations document variation between calls given the same prompt.

The 15/16 tie depends on the equal weight given to repair and preservation. If repair gets three quarters of the weight, the recorded late-arm score exceeds the early-arm score by 6.25 percentage points. Giving preservation three quarters reverses the difference. These are two ways to score the same observations. Neither estimates how changing diagnostic timing would affect a new run.

## An extra turn can repair a bug the display never showed

We forked all 16 CPython histories at the first edit. Four contained the same faulty Luna edit, and twelve held working code. Each branch kept the original exchange, current source, model and edit options, and received one more decision. We showed the actual output from one dictionary. The larger key was inserted first and the two distinct values occupied the same insertion positions across probes. The new execution came without an expected output or verdict. We scored the final code on ten held-out checks of order and bindings.

**Table 6. Recovery and preservation after one more decision on CPython.** Only the keys 2 and 10 exposed the sorting error in the displayed output. We scored each final implementation on ten held-out checks of key order and key–value bindings.

| Keys shown | Key order printed by faulty code | Faulty states repaired | Working states preserved |
| --- | --- | --- | --- |
| 1 and 2 | 1 then 2 | 4/4 | 12/12 |
| 2 and 10 | 10 then 2 | 4/4 | 12/12 |

The faulty implementation and a working one printed indistinguishable output for keys 1 and 2. With keys 2 and 10, the faulty formatter printed 10 first. All four faulty states recovered under each probe. Both conditions preserved functionality in all twelve working states, although agents replaced the implementation in four of twelve cases with keys 1 and 2 and six of twelve with keys 2 and 10. Exposing the wrong order added zero observed repairs in this sample. Four histories of one defect on one task give little information about how often other defects require a revealing example.

When we later restored these sixteen histories with previously unseen key pairs (3/7 or 3/20), a further decision without any new display repaired two of the four faulty starts. Either display repaired all four and preserved all twelve working starts (Table S1). Across seven fresh starting implementations from dateutil and CPython, revealing output and no output produced identical source choices in all fourteen model–source pairs (Table S2). Only the shared, positive-offset display preceded the dateutil regression. Clearing the conversation and changing the starting programs also changed the population of decisions.

## How often does the same agent disagree with itself?

A single sample per condition can make ordinary variation look like a response to feedback. For each of the same sixteen CPython histories, we scheduled two independent sessions with no new display and two with a correct-looking display. The literal prompt bytes matched within each condition. Each complete history contributes four comparisons across displays and two within displays. We evaluate disagreement twice, once on which implementation was selected and once on whether it passed. Table 7 subtracts the within-display rate from the cross-display rate, weighting histories equally.

Of 16 enrolled histories, 14 supplied all four usable decisions. Without the new display 4/8 faulty draws recovered and 24/24 working draws passed. With the display the counts were 5/7 and 23/23. The four faulty starting histories repeat the same Luna edit. Both the number of distinct defects and the number of complete histories matter when interpreting these rates. Across all sixteen histories, filling unobserved choices with any offered implementation bounds the source estimate between −1.6 and +7.8 percentage points. Every possible completion gives the same functional estimate of −3.125 points. We also enumerated all six allocations of the two display labels within each complete four-response history, conditioning on its observed choices. Exact upper-tail probabilities adjusted over the source and functional outcomes were 1 and 1. This secondary calculation assumes that labels are exchangeable within histories under the null. We specified it during collection before inspecting the duplicate-prompt choices.

**Table 7. Disagreement on identical CPython histories. Percentages in the first two outcome columns are mean disagreement rates. The final column is their signed difference in percentage points.**

| Endpoint | Cross-display | Within-display | Excess (points) |
| --- | --- | --- | --- |
| Selected implementation | 30.4% | 28.6% | +1.8 |
| Held-out pass | 10.7% | 14.3% | -3.6 |

Under independent draws from a stable response distribution in each condition, the expected difference equals half the sum of the squared changes in probabilities of choosing each implementation. With a binary grade it reduces to the squared change in pass probability. This is a categorical instance of a two-sample discrepancy (Gretton et al., 2012). Sampling can give a negative estimate. The statistic measures a change in the distribution of choices. The separate counts of repairs and regressions give its direction.

## Related work

Execution feedback can improve repair. Olausson et al. (2024) found that the gains varied with task and cost and increased when a stronger model supplied feedback. Kim (2026a) found that giving a concrete failure raised repair rates over providing a failure status alone. In a separate study without execution feedback, Kim (2026b) recorded both repair and regression from common starting programs. Iscan (2026, preprint) compared execution facts with generic prompts and blind resampling. The advantage depended on the comparison. These studies motivate a narrower question about a particular successful edit. Had the observation arrived in time, and could its contents distinguish the faulty implementation from a working one?

Gao et al. (2026) forked identical programs under current and stale traces. A policy that prevented observed damage to working programs also reduced repair of faulty ones. FixedBench (Gloaguen et al., 2026) tests whether agents edit repositories in response to issues already resolved. ImpossibleBench (Zhong et al., 2026) creates conflicts between specifications and tests, while COBALT (Z. Chen et al., 2026) examines robustness to misleading execution feedback. Our comparisons add two controls for different questions. Repeated draws estimate how much a choice varies with identical input. A paired reversal asks whether the model can implement both assigned contracts on unchanged source.

Weyuker (1982) identified an assumption behind ordinary testing: someone must be able to judge whether an observed output is correct. In programming by example, Jha et al. (2010) ask for the target program’s output on an input where two candidate implementations disagree. An execution of the *current* program answers a different question: it tells the agent what that program does. We use both kinds of observation and record their source. A truthful execution may reveal a bug when the intended ordering is already specified. A trusted target example can instead tell the agent which ordering is intended.

Counterfactual tasks have a direct precedent. Wu et al. (2024) evaluated models after altering familiar assumptions and found a performance drop on the altered tasks. Jia et al. (2025) used input–output examples to resolve ambiguity in natural-language programming problems by revising the descriptions. In our benchmark reversal the language semantics and source stay fixed. We name both conventions, change one required output, and grade the returned patch against each contract. This evaluates whether a model follows a disambiguating example when the familiar correction would be wrong for the caller.

There is a further reason to care who supplied a value. In experiments on human learning, Shafto et al. (2014) modeled the examples people choose when they intend to teach. Pu et al. (2020) applied the same idea to synthesizing programs from user examples. A developer who supplies an expected answer may be communicating a requirement through that choice. A runner that prints an actual answer can produce exactly the same value without knowing what the developer intends. The identical-value comparison measures whether this distinction changes an agent’s code choices.

## What the experiments establish

The same code can be a successful repair or a regression, depending on the contract the caller supplied. A benchmark with a single fixed specification can correctly reject a program that fulfills a different specification. The paired reversal allows us to grade each returned program under both contracts, then ask whether changing one required output elicited the corresponding change in behavior. The all-or-nothing pair score rules out always producing the familiar correction. On all eight completed caption comparisons, the models followed both values even when told only that an unspecified candidate had printed them. Following an example across two different values is therefore insufficient evidence that the agent recognized it as a requirement.

Matplotlib illustrates a separate dependency. The usefulness of an input depends on the failure one is trying to detect. A test selected because it separates a defective program from the maintainer's fix can pass the new regression an agent writes in response. Separating repair and preservation exposed that event. Retaining both versions let us run the same two inputs before and after the edit and explain exactly how the test lost its power.

The experiments have deliberately narrow boundaries. Four inspected algorithms provided four coherent alternative contracts. We cannot estimate how often ordinary bugs admit such an interpretation, or whether the models had seen these public benchmark corrections. We described both alternatives, localized each patch to one expression and verified it on finite domains. The models saw extracted functions for the two maintenance fixes. The independent Matplotlib replay covers one public axis operation on one historical defect. The authored tasks offer only two implementations. We sampled hosted service aliases within one account window, with no independently reviewed case admission. Session order was balanced or randomized within the specified schedules. Hidden provider coupling or changes over time could still affect the duplicate-draw comparison. The results describe measured editing choices in these tasks. On unseen repositories a stronger test would have an independent maintainer specify the intended behavior before a model sees the issue, allow the model to find its own edit location, and keep the original working program as a control.

To credit a repair to feedback, keep the pre-edit program and repeat the decision with the same opportunity to act. Record whether the message reported an execution or specified a requirement. Once the agent changes the program, the diagnostic value of the old test is itself an empirical question.

## Data and contributions

The reviewer packet includes plans, assignments, responses reduced to the observed editing decision, grading records, input-domain specifications and an offline script that rebuilds the seven main result tables from the released choices. Table S4 and Figure S2 can be traced to 78 archived decisions. The original 64 timing decisions and 32 early CPython probe decisions remain identifiable in their original cohorts. Each ledger preserves assigned cells even when no response was collected. The studies shared a subscription window. Investigators chose which study received the next available block as results arrived. After the first eight identical-value blocks they scheduled a fresh test of the sampling explanation and prioritized a second already ordered wave of the original caption study. The order within each study stayed fixed.

Across these follow-ups, 366 of 888 assigned calls have native response records and 364 supplied a usable decision. Usage counters are available for 366. They report 5,752,840 input tokens including 4,821,632 cached tokens and 4,775 output tokens. These counts cover the full hosted sessions. Two responses could not be scored. The service replaced the original weekly quota identifier before its previously reported expiry and the remaining assignments were left unstarted. The 138 earlier CPython, cross-project and reference-example choices remain in separate ledgers.

Codex assisted with experiments, analysis and drafting. Human author approval and an external deposit are pending.

## References

Xinyun Chen, Maxwell Lin, Nathanael Schaerli, and Denny Zhou. 2024. Teaching Large Language Models to Self-Debug. *International Conference on Learning Representations (ICLR).* [Conference paper](https://proceedings.iclr.cc/paper_files/paper/2024/hash/2460396f2d0d421885997dd1612ac56b-Abstract-Conference.html)

Ziru Chen, Dongdong Chen, Ruinan Jin, Yingbin Liang, Yujia Xie, and Huan Sun. 2026. COBALT: Contextual Bandit Learning with Offline Trajectories for Multi-Turn Code Generation. *Transactions on Machine Learning Research.* [Journal paper](https://openreview.net/forum?id=7SwoUNzIxe)

Arthur Gretton, Karsten M. Borgwardt, Malte J. Rasch, Bernhard Schölkopf, and Alexander Smola. 2012. A Kernel Two-Sample Test. *Journal of Machine Learning Research* 13, 723–773. [Journal paper](https://www.jmlr.org/papers/v13/gretton12a.html)

Xueping Gao, Jianwei Yang, and Qiang Yang. 2026. Looping Is Not Reliability: State-Bound Evidence and Typed Revision Contracts for Agentic Code Repair. *International Workshop on Agentic AI for Next-Generation Software Development (AgenticDev).* [Author manuscript, arXiv:2607.24604v3](https://arxiv.org/abs/2607.24604v3)

Thibaud Gloaguen, Niels Mündler-Sasahara, Mark Niklas Müller, Veselin Raychev, and Martin Vechev. 2026. Coding Agents Don’t Know When to Act. *Conference on Language Modeling (COLM).* [Conference paper](https://proceedings.colm.cc/paper_files/paper/2026/hash/b328c5bd9ff8e3a5e1be74baf4a7a456-Abstract-Conference.html)

Mehmet Iscan. 2026. Falsification, Not Exposure: An Internally Preregistered Placebo-Controlled Decomposition of Self-Repair Feedback in Frozen Small Code Models. *arXiv preprint.* [arXiv:2606.31511](https://arxiv.org/abs/2606.31511)

Carlos E. Jimenez, John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press, and Karthik Narasimhan. 2024. SWE-bench: Can Language Models Resolve Real-World GitHub Issues? *International Conference on Learning Representations.* [Conference paper](https://openreview.net/forum?id=VTF8yNQM66)

Susmit Jha, Sumit Gulwani, Sanjit A. Seshia, and Ashish Tiwari. 2010. Oracle-Guided Component-Based Program Synthesis. *ACM/IEEE International Conference on Software Engineering (ICSE)*, 215–224. [Conference paper](https://doi.org/10.1145/1806799.1806833)

Haoxiang Jia, Robbie Morris, He Ye, Federica Sarro, and Sergey Mechtaev. 2025. Automated Repair of Ambiguous Problem Descriptions for LLM-Based Code Generation. *IEEE/ACM International Conference on Automated Software Engineering (ASE).* [Author manuscript](https://discovery.ucl.ac.uk/id/eprint/10225137/1/SpecFix.pdf)

Jindae Kim. 2026a. Inducing Code Change in LLM Self-Debugging: Effects on Program Repair. *AI* 7(10), article 392. [Journal paper](https://www.mdpi.com/2673-2688/7/10/392)

Jindae Kim. 2026b. Understanding Regression in Code Self-Refinement: A Study of Refinement Protocols Without Execution Feedback. *AI* 7(10), article 416. [Journal paper](https://www.mdpi.com/2673-2688/7/10/416)

Derrick Lin, James Koppel, Angela Chen, and Armando Solar-Lezama. 2017. QuixBugs: A Multi-Lingual Program Repair Benchmark Set Based on the Quixey Challenge. *SPLASH Companion*, 55–56. [Conference paper](https://doi.org/10.1145/3135932.3135941)

Theo X. Olausson, Jeevana Priya Inala, Chenglong Wang, Jianfeng Gao, and Armando Solar-Lezama. 2024. Is Self-Repair a Silver Bullet for Code Generation? *International Conference on Learning Representations (ICLR).* [Conference paper](https://proceedings.iclr.cc/paper_files/paper/2024/hash/9ddc141bdbf9d1db510cefff56c586ad-Abstract-Conference.html)

Jinjun Peng, Leyi Cui, Kele Huang, Junfeng Yang, and Baishakhi Ray. 2025. CWEval: Outcome-driven Evaluation on Functionality and Security of LLM Code Generation. *IEEE/ACM International Workshop on Large Language Models for Code (LLM4Code).* [Workshop paper](https://ieeexplore.ieee.org/abstract/document/11028476)

Yewen Pu, Kevin Ellis, Marta Kryven, Josh Tenenbaum, and Armando Solar-Lezama. 2020. Program Synthesis with Pragmatic Communication. *Advances in Neural Information Processing Systems* 33. [Conference paper](https://proceedings.neurips.cc/paper/2020/hash/99c83c904d0d64fbef50d919a5c66a80-Abstract.html)

Zichao Qi, Fan Long, Sara Achour, and Martin Rinard. 2015. An Analysis of Patch Plausibility and Correctness for Generate-and-Validate Patch Generation Systems. *ACM International Symposium on Software Testing and Analysis (ISSTA).* [Conference paper](https://doi.org/10.1145/2771783.2771791)

Patrick Shafto, Noah D. Goodman, and Thomas L. Griffiths. 2014. A Rational Account of Pedagogical Reasoning: Teaching by, and Learning from, Examples. *Cognitive Psychology* 71, 55–89. [Journal paper](https://doi.org/10.1016/j.cogpsych.2013.12.004)

Mark Vero, Niels Mündler, Victor Chibotaru, Veselin Raychev, Maximilian Baader, Nikola Jovanović, Jingxuan He, and Martin Vechev. 2025. BaxBench: Can LLMs Generate Correct and Secure Backends? *International Conference on Machine Learning (ICML)*, PMLR 267, 61344–61390. [Conference paper](https://proceedings.mlr.press/v267/vero25a.html)

Elaine J. Weyuker. 1982. On Testing Non-Testable Programs. *The Computer Journal* 25(4), 465–470. [Journal paper](https://doi.org/10.1093/comjnl/25.4.465)

Ratnadira Widyasari, Sheng Qin Sim, Camellia Lok, et al. 2020. BugsInPy: A Database of Existing Bugs in Python Programs to Enable Controlled Testing and Debugging Studies. *ESEC/FSE Tool Demonstrations*. [Conference paper](https://doi.org/10.1145/3368089.3417943)

Zhaofeng Wu, Linlu Qiu, Alexis Ross, Ekin Akyürek, Boyuan Chen, Bailin Wang, Najoung Kim, Jacob Andreas, and Yoon Kim. 2024. Reasoning or Reciting? Exploring the Capabilities and Limitations of Language Models Through Counterfactual Tasks. *NAACL*, 1819–1862. [Conference paper](https://aclanthology.org/2024.naacl-long.102/)

Ziqian Zhong, Aditi Raghunathan, and Nicholas Carlini. 2026. ImpossibleBench: Measuring LLMs' Propensity of Exploiting Test Cases. *International Conference on Learning Representations (ICLR).* [Conference paper](https://proceedings.iclr.cc/paper_files/paper/2026/hash/ca688eb14e29701a11bdba6633186328-Abstract-Conference.html)

## Supplement A. Complete cohorts behind the earlier editing comparisons

![Figure S1. What a coding agent saw before making its next choice. At left are the three actual continuations from one archived GPT-6 Luna edit in CPython. The left panel shows the key order from each displayed dictionary. At right the same model starts with the midpoint-down rule in a separate task. The example states which result the target installation requires. Each row is one fresh decision. Tables S1 and S3 give the complete cohorts.](figures/feedback_example.png)

We selected all sixteen CPython first-edit histories from an earlier timing experiment on the standard library formatter (Table 5). Four held the same faulty edit by GPT-6 Luna. Twelve held working code. In an earlier fork (Table 6), the four faults were repaired both when the new output showed the wrong order and when it appeared correct. We returned to the sixteen histories and scheduled three fresh continuations per history to measure what a display added to the opportunity to edit again. One omitted the new execution paragraph. Another showed the current formatter’s output for keys 3 and 7. A third showed its output for 3 and 20. Both inputs were new to the archived exchange. The code, previous messages, menu, model and single remaining decision were identical within a history. All three branches retained any diagnostic already seen. The two displays used the same values and insertion positions. The 3-and-7 probe agreed with working code on the sorting fault but could still reveal an incorrect key–value binding in another implementation.

We froze the inputs, ten held-out checks, schedule and prompt hashes locally before any of the 48 calls. Dispatch order was counterbalanced within model and starting-correctness groups. The earlier two-arm results and the sorting defect were already known when we designed this follow-up. The planned primary comparison is paired recovery from the four faulty states with the revealing display versus no new display. Astra contributed only working checkpoints in this series. Across both models there was one underlying sorting defect.

**Table S1. A further decision with or without fresh execution output.** All 48 scheduled decisions were scored. Each row starts from the same four faulty and twelve working checkpoints. The last column counts a change of source that still passes.

| New display | Faulty states repaired | Working states preserved | Working states rewritten and passing |
| --- | --- | --- | --- |
| No new output | 2/4 | 12/12 | 4/12 |
| Keys 3 and 7 | 4/4 | 12/12 | 3/12 |
| Keys 3 and 20 | 4/4 | 12/12 | 4/12 |

Both output conditions repaired the same two additional histories. In each, Luna explicitly kept the faulty text sort when no fresh output was shown. With either display it selected the same passing replacement. In the other two faulty histories it recovered in all three conditions. Even where the grades matched, the edits could differ. Between the two displays the model selected different implementations on two of four faulty starts and three of twelve working starts.

Showing the wrong order was unnecessary for the two additional observed recoveries. The display that looked correct also contained the key–value bindings and a statement that the current implementation had been executed. X. Chen et al. (2024) showed that models could correct code by examining executions and explaining the program even without being told whether its output was correct. The comparison cannot separate the contribution of those contents from that of receiving an execution message. One choice per condition on four histories of a single defect gives little precision about the frequency of either response.

The menu puts the scores in perspective. Each state offered four implementations through one keep action and three replacements. Two passed all ten checks. Keeping every first edit would repair 0/4 faults and preserve 12/12 working states. Restoring the source from before the first edit would repair all 4/4 faults but preserve only 4/12 working states. Luna had introduced the same fault in four initially working states, so returning to their earlier source necessarily repaired all four. An evaluator with advance knowledge of a passing implementation could score perfectly in both strata without reading any new output. These are properties of the menu and the archived starting states.

## Fresh starting implementations

The four faulty histories in Table S1 repeat a single implementation. We therefore took every implementation from the original dateutil and CPython menus. In dateutil, two variants miscomputed a negative UTC offset and one passed the six held-out checks. In CPython, one variant misbound values to sorted keys, one sorted integer keys as text, and two passed. Each model encountered each source in a fresh prompt with the specification, edit menu and one decision. No prior diagnostic or editing history was supplied. The change of both starting states and conversation prevents a direct estimate of the effect of history. Within this new series, every starting state appears in all three conditions.

The three arms gave no new execution, a display on which every implementation agreed, or a display distinguishing every faulty implementation from the reference. We ran each starting program to obtain the displayed output. All dateutil variants returned 12,000 seconds for +03:20. For −03:20, the reference returned −12,000 seconds and the faulty variants returned +9,600 and −9,600. On CPython, inserting key 20 before 3 exposed the ordering or the binding error, depending on the starting source. We froze the inputs, held-out checks and dispatch order before collecting these decisions.

**Table S2. Starting each implementation in a fresh session.** Both models encountered each source under all three conditions. The denominators count model–source combinations within the project and starting state.

| Project | Display of current code | Defects repaired | Working starts preserved |
| --- | --- | --- | --- |
| dateutil | None | 4/4 | 2/2 |
| dateutil | Shared output | 4/4 | 1/2 |
| dateutil | Revealing output | 4/4 | 2/2 |
| CPython | None | 4/4 | 4/4 |
| CPython | Shared output | 4/4 | 4/4 |
| CPython | Revealing output | 4/4 | 4/4 |

All 42 calls returned a valid choice. Every arm repaired all eight faulty model–source combinations. In the prespecified comparison of revealing output versus no output, the models selected exactly the same final implementation in all fourteen blocks, including all six working starts. Both models converged on the same formatter in every CPython condition. This left no margin for additional repairs on the four source defects in this panel.

The only difference in functionality occurred on a working dateutil start. Luna saw that +03:20 produced the correct offset of 12,000 seconds, then replaced the parser with one that agreed on that case. It failed three held-out negative offsets: for example, it read −05:00 as +05:00. The other two conditions kept the original parser on that start. Thus even a truthful, correct-looking display preceded a harmful edit in one matched block. One sampled decision gives no estimate of how often this display would damage working code. The edited source and the three failed checks are available in the reviewer archive.

## A positive control for choosing between two programs

A printed result can show what a program does. Sometimes the missing information is what it ought to do. We designed an exploratory positive control using three tasks with two permitted conventions each: numeric or decimal-text ordering of integers, the first or last occurrence of a tied maximum, and upward or downward rounding at an exact midpoint. Each version has a fully specified reference and a supplied implementation. The installation’s convention is hidden. For example, both rounding rules take 12 to 10, but one takes 25 to 20 and the other takes it to 30. A trusted example in this experiment states the required output for the target installation.

For each task, starting implementation and model, we held the wording, two code choices and input fixed across the two distinguishing prompts and changed the required output alone. The action was to keep the current implementation or switch to the other. Two further prompts either omitted the example or supplied an example on which both rules agreed. Each of those prompts was identical across the two possible target rules, so we obtained one decision and scored it under both. Every valid shared decision must pass for exactly one of its two target rules. The empirical test is whether changing the required output changes the choice in the correct direction on *both* members of the distinguishing pair. Six separate held-out cases graded each contract. The sources, calibration and randomized order were frozen before dispatch.

**Table S3. Choosing an implementation under two possible target rules.** For the first two rows each choice is assessed against both targets. The distinguishing condition makes one call per target. Repair and preservation are scored under the assigned target.

| Reference example | Valid / scheduled calls | Defective starts repaired | Working starts preserved |
| --- | --- | --- | --- |
| None | 12/12 | 2/12 | 10/12 |
| Shared example | 12/12 | 3/12 | 9/12 |
| Distinguishing example | 24/24 | 12/12 | 12/12 |

All 48 calls yielded valid choices, producing 72 target assessments. Within all twelve model–task–start blocks, the model selected the appropriate implementation for *both* distinguishing outputs. For the same rounding code and the same input 25, requiring 20 selected the midpoint-down rule, while requiring 30 selected the midpoint-up rule. This held with either starting implementation and for both models.

With no example, the models kept the starting code in ten of twelve calls. With a shared example, they kept it in nine. Those preferences are observed behavior. The total of twelve passes in twenty-four assessments in either row follows arithmetically because the two possible target conventions have equal weight and require opposite choices. The twelve correct *paired* responses with distinguishing outputs establish that these configurations could use an authoritative example in this bounded setting. The control does not test whether they would seek such an example themselves.

## Supplement B. Observed stopping and a prospective experiment

In the historical experiment, Qwen3 4B produced policies for authored tasks. We selected 14 paired continuations from ten families in which the agent had already produced a candidate satisfying the bounded specification. Each pair shared its starting candidate and prior history. One branch received truthful feedback, the other persistent false failures. All branches knew they had at most three decisions. The 78 observed decisions belong to 28 continuations of 14 starts.

**Table S4. Selected persistent-verdict cohort.** Fourteen paired onsets from ten families. The denominators for the first four rows are 14 arms per condition. The last row counts submissions.

| Observable outcome | Truthful PASS | False FAIL |
| --- | --- | --- |
| Early voluntary stop | 3 | 0 |
| First action was inspection | 0 | 12 |
| Any post-onset regression | 8 | 7 |
| Terminal regression | 5 | 7 |
| Additional submissions | 28 | 17 |

Across three decisions, each condition entered failure eight times. They differed in how branches left failure. On the last decision, five of the eight failing truthful branches submitted again. Three recovered by submitting a candidate that had passed earlier. Two returned to their first-decision candidate, one to the starting candidate. All six false-failure branches entering the last decision with faulty code inspected it. Inspection returned the current candidate and a generic message and consumed the last decision. The only recovery under false feedback preceded a relapse.

![Figure S2. Failing candidates after each decision (top) and paired outcomes at decisions two and three (bottom). Each curve follows 14 branches. In the matrix, each matched pair contributes to one cell. Diagonal cells retain their joint outcome. Three pairs gained a second passing branch and one lost a passing branch. Every agent knew the three-decision limit.](figures/observed_horizon.png)

The aggregate ranking reversed between decisions two and three. At decision two, 8/14 truthful and 6/14 false-failure branches held a failing candidate. At decision three, the counts were 5/14 and 7/14. Yet in none of the fourteen matched pairs did the sole passing arm switch sides. In three pairs only the false-failure branch passed at decision two and both passed at decision three. In a fourth pair both passed first and only the truthful branch passed last. The other ten pairs stayed in the same joint state. Four families accounted for the four changes.

With equal weight per family, the excess fraction failing under false feedback moved from −15 to +15 percentage points. The sign change survived each of ten leave-one-family-out recalculations. With equal weight per pair it survived nine exclusions, with a tie at decision two when the nonce-uniqueness family was omitted. These recalculations reuse the same selected families. They measure the sensitivity of the descriptive contrast to family composition. All agents had been told the same three-decision limit, so stopping the analysis at decision two cannot identify the effect of announcing a shorter budget.

Only two of the fourteen pairs allowed the same permitted and prohibited cases to be scored separately. Both conditions still served all three required cases at termination. The truthful branches accepted one of seven prohibited cases, the false-failure branches five of seven. The other twelve pairs have only a combined outcome under this comparison.

The end of a run also requires evidence. In a preceding audit of 40 local runs, the controller issued 38 self-termination labels after exhausting its reminders. Thirteen of those records also contained an acknowledged agent request. In nine of twenty runs under a hidden acceptance veto, the last candidate passed the implemented family checks and was rejected anyway. We also examined two public SWE-bench Verified series covering the same ten issues. In the SWE-agent series, the trace established an explicit agent request to stop in two cases and a cost limit in six. The cause remained unresolved in two cases there and in all ten OpenHands episodes. We count an early voluntary stop only when the controller honors a task-specific terminal action before the last permitted decision.

The historical reversal motivates a different planned experiment. At the first verified repair, the controller will copy the candidate and transcript into four branches, cross a truthful PASS or false FAIL with an announced and enforced allowance of two or three decisions, and give truthful later feedback. The outcome is whether the retained candidate passes when the branch ends. The interaction subtracts the gain from allowing a third decision under PASS from the corresponding gain under FAIL. This design tests the combined effect of announcing and enforcing the budget. It also records early termination and incomplete runs.

The candidate schedule spans four hosted models, nineteen families, three prompt variants and five repeats. Conditional on reaching a verified repair, the plan gives families equal weight and applies Holm’s adjustment to four model-specific comparisons. With 50% of precursors reaching a verified repair, 5% independent loss per branch, partially coupled outcomes and within-family interaction correlation of 0.2, simulations detected ten- and twenty-point negative interactions in 8.5% and 36.4% of runs. At zero within-family correlation the figures were 29.0% and 88.7%. Independent case review and registration are pending. No confirmatory model episodes have been collected.

## Supplement C. One-shot verdicts

**Table S5. One-shot follow-ups.** Each pair received a single truthful or false initial verdict, then followed the same continuation protocol. These small waves were scheduled sequentially.

| Cohort | Verified pairs / precursors | Early stop, PASS / FAIL | Terminal regression, PASS / FAIL |
| --- | --- | --- | --- |
| First wave | 3 / 4 | 3 / 2 | 0 / 1 |
| Subsequent families | 2 / 4 | 1 / 1 | 1 / 1 |

The one-shot waves in Table S5 delivered the changed verdict once. An authorization trajectory in the first wave repeated an earlier deterministic path. Both arms of a signature-policy task in the next wave finished with the same failing policy. In two further waves of four authorization pairs each, seven arms regressed, all by denying a legitimate request. In a separate six-pair follow-up, two branches of one key-rotation task both failed. One denied a current key and the other accepted a retired key. A single failure count would give those policies the same score. In six further matched blocks on unsatisfiable tasks, both explanations produced two submissions per arm and zero early stops. Two voluntary stops came on the final permitted decision.

## Repeating a command in a public repository trace

We examined all twenty previously reserved SWE-bench Verified episodes, ten matched issues in each of two submissions, to see how much of a repair trajectory can be reconstructed from an ordinary command log (Jimenez et al., 2024). Eighteen public trajectories matched their recorded digests. Our locally frozen rule admitted single-line test-runner and Python-script invocations. Four of eight available SWE-agent episodes and zero of ten OpenHands episodes repeated identical command text. A post-hoc sensitivity check also admitted a literal change of working directory immediately before the invocation, retaining the directory in the identity of the command. The OpenHands count rose to four of ten. Under either rule no repeated command had both a recognizable initial and final test-suite verdict. These counts describe the forms the parser recognized.

One OpenHands episode illustrates why a process exit needs its own outcome. On Matplotlib issue 25479, the agent ran the same script three times. The first two runs raised a colormap exception. After a second source edit the third run exited successfully. The trace records no edit to that script between its invocations. It contained no assertion about the required behavior, and the independent benchmark evaluator marked the issue unresolved. The disappearance of the exhibited exception is a reproducible observation. Whether the agent would have made the same edit without seeing the failure requires another comparison. [Published trajectory](https://swe-bench-submissions.s3.amazonaws.com/verified/20241029_OpenHands-CodeAct-2.1-sonnet-20241022/trajs/matplotlib__matplotlib-25479.json)

## Supplement D. Calibration of the finite-policy checker

The Python patch experiments evaluate specified functional behavior. The historical policy studies also record acceptance of prohibited cases and denial of required ones where the policy exposes both outcomes. CWEval (Peng et al., 2025) and BaxBench (Vero et al., 2025) likewise evaluate secure and functional behavior separately. The finite-policy instrument records the outcome of an example test, a separate bounded reference and the verdict displayed for the same submitted candidate. It evaluates typed policies in a separate process. The historical free-form evaluator had a different interface. Table S6 shows how often an example test missed a policy that violated its bounded specification.

**Table S6. Calibration before model collection.** Each row below covers every enumerated policy in one v7 family under truthful checking. “Caught” counts invalid policies rejected by the example test. The reference column gives erroneous rejections by the normal acceptance gate. Each of these eight families has one correct policy in the enumerated language.

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

Across 20 families and 28 family-version combinations, the examples caught 285 of 354 invalid policies. The normal acceptance gate rejected all 354 and accepted all 36 valid references. Under the injected rejection rule all 36 valid references received a failure despite passing the examples. These counts characterize the enumerated policies and the instrument used in the experiment. Estimating a scanner’s false-alarm rate in use would require a sample of real submissions.

We separately calibrated functional and security-related observations on two specifications adapted from CWEval. For a file-permissions task and a password-derivation task, the controls distinguished all four combinations obtained by corrupting either observation, both, or neither. Four distinct but predictable salts passed a nonrepetition check, illustrating the limit of that security observation. These were authored observation controls. The Python studies measure functionality on specified inputs. [CWEval file specification](https://github.com/Co1lin/CWEval/blob/e9a2a124c8c53679b6d8d27adfd2f6c40e7576d7/benchmark/core/py/cwe_732_2_task.py) · [CWEval password specification](https://github.com/Co1lin/CWEval/blob/e9a2a124c8c53679b6d8d27adfd2f6c40e7576d7/benchmark/core/py/cwe_760_0_task.py)

## Supplement E. Effort and correctness on arithmetic tasks

A lookup table for doubling the integers 0 through 3 makes the intended behavior fully visible. Each agent received a correct table or one with a single faulty entry and the same initial failure message. It could request a check that repeated the message or ran an independent test of selected entries. Scripted controls illustrate the tradeoff. Always stopping preserved all six working cases per condition and repaired none of six defects. Checking once and using an ideal rewrite on failure repaired all six defects with the repeated verdict. The partial check spared six unnecessary rewrites while missing three defects.

In a preliminary eight-episode run per configuration, GPT-6 Sol and GPT-6 Luna each repaired four defective starts and preserved four working ones. Every repair came on the first decision. All four requested checks evaluated correct tables. The two configurations used 13 and 18 decisions respectively. Three planned Claude configurations supplied no episodes because authentication failed.

We repeated the experiment at low and high reasoning effort for eleven selectable Codex aliases. Across 176 new episodes and 324 decisions, all 88 defective starts were repaired on the first action and all 88 correct starts remained correct throughout. Every one of the 41 requested checks evaluated an already correct table. This rules out those replies as the source of any first repair. The initial failure message, visible specification and edit actions were already available. At higher effort, unchanged resubmissions fell from 27 to 7 and explicit stops rose from 77 to 84.

A separate six-task panel examined computation within one decision. Each configuration received six tables in a single request, three working and three defective. A separate implementation checked the answers for 20 inputs. We could score 374 of 384 tables across 64 supported configurations. Of 62 fully scorable replies, 50 solved all six tasks. The CLI records the requested model alias. The provider supplied no independent deployment identifier.

**Table S7. Effect of increasing the requested reasoning effort on six fixed tasks.** Counts compare each model to itself. A changed task gained or lost correctness on the same input table. The last column is the median within-model difference in reported reasoning tokens for the complete six-task prompt.

| Effort change | Models with a full pair | Tasks gaining / losing correctness | Median token change |
| --- | --- | --- | --- |
| low to high | 9 | 3 / 1 | +174 |
| xhigh to max | 11 | 0 / 0 | +293 |
| max to ultra | 9 | 0 / 0 | −300 |

Increasing effort from xhigh to max increased the reported reasoning-token count for all eleven models, while all 66 matched model–task outcomes stayed the same. Both Luna aliases made the same harmful change to a correct queue table at both settings. The nine aliases supporting ultra had already solved all six tasks at xhigh. Eight used fewer reasoning tokens at ultra than at max. Each setting contributed one reply. Figure 3 records the realized cost and score, including incomplete responses.

![Figure 3. Correct tables (left) and reported reasoning tokens (right) for 11 Codex models across 64 supported settings. Each setting received the same six tasks in one request. Fractions count correct tables among those that could be scored. A star marks a partial score, fmt means no table could be scored, and n/a marks an unsupported setting.](figures/effort_panel.png)

## Supplement F. Collection coverage

Table S8 accounts for each new scheduled decision exactly once across the follow-up studies. The first 138 choices in Supplement A and the original timing pilots have their own rosters. A model–task pair can appear in several studies. Each row in Table S8 uses its own frozen assignment roster. Raw response hashes link observed assignments to recorded sessions. The underlying usage records count full native sessions, including cached context.

**Table S8. Scheduled, captured and usable follow-up calls.** Each usable response contributes one native editing decision.

| Study | Scheduled | Captured | Usable |
| --- | --- | --- | --- |
| Actual and required output | 168 | 84 | 84 |
| QuixBugs expression patches | 48 | 48 | 48 |
| Historical maintenance fixes | 24 | 24 | 24 |
| CPython duplicate draws | 64 | 64 | 62 |
| Same value, different sources | 448 | 56 | 56 |
| Opposing QuixBugs contracts | 48 | 48 | 48 |
| Matplotlib repeated prompts | 24 | 24 | 24 |
| QuixBugs definitions omitted | 32 | 18 | 18 |
| Disclosure of example selection | 32 | 0 | 0 |

## Supplement G. Why the four published defects implement other contracts

In the sorting program the left recursion receives the values below the pivot and the right recursion receives those strictly above it. The pivot itself appears once in the result. Induction on input length gives one occurrence of every distinct integer in sorted order. Restoring equality to the right partition preserves multiplicities.

In the maximum-sum program the defective update adds each new item to the accumulated total without resetting. Successive totals are precisely the prefix sums. The returned maximum starts at zero, so the empty prefix is available. The benchmark correction allows the running total to reset at zero, which permits a maximizing contiguous sublist to start later.

The parentheses program immediately rejects a negative running depth. Any surviving prefix of final depth d can be completed by appending d closing parentheses. Returning true at the end therefore tests whether completion remains possible. Returning whether d equals zero tests whether the string is already complete.

For knapsack, take positive integer item weights and nonnegative integer capacity. The zero-initialized row permits the empty choice, including at zero capacity. If the defective guard takes an item of weight w at capacity j, it requires w strictly below j and leaves strictly positive capacity j − w. Induction over processed items then bounds the total weight of every nonempty chosen packing strictly below j, and each feasible nonempty packing can be constructed this way. The skip branch and the maximizing update select the highest value. Allowing equality recovers the benchmark contract. These arguments concern the published starting implementations. The numerical checks for arbitrary generated expressions retain their stated finite domains.
