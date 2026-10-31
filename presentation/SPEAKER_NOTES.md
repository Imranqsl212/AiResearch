# Research update — speaker notes

**Deck:** `Research_Update_2026-11-01.pptx`

**Audience:** people without a cybersecurity or AI background

**Length:** about 7–8 minutes, followed by questions

**Presenter:** Imran Zakirov

The deck separates four kinds of material: the completed **40-episode historical
audit**, **authored calibration cases**, a separate **30-episode excluded pilot**,
and the **planned main experiment**. Do not combine their denominators. The
presentation does not claim that passing a finite test proves general security.

## Slide 1 — The Tests Passed. The Benchmark Said No.

“Our research looks at AI coding assistants that try to fix security problems.
We found a surprising problem with how one local benchmark judged them: some
final submissions passed its implemented tests, but its final verdict was
`FAIL`. Today I’ll show what we found, why it matters, and what we need to test
next.”

**Source:** [README](../README.md), [historical paper](../paper/final.md).

## Slide 2 — Imagine a teacher with a checklist

“Imagine a teacher whose checklist says every listed requirement is satisfied,
but the final grade is still fail because of another rule. A student might
respond to that grade by changing the work. The analogy helps explain the
problem. A checklist can also be incomplete: passing it does not establish
that the work is perfect.”

**Source:** This is an analogy of the evaluator design described in the
[historical paper](../paper/final.md).

## Slide 3 — An AI coder responds to the checker

“The agent receives a small security task, proposes code, sees checker
feedback, and can revise or stop. If we want to understand its behavior, we
need to know exactly what the checker measured and what feedback the agent
actually saw. The final pass rate alone hides those steps.”

**Source:** [paper Methods](../paper/final.md).

## Slide 4 — One recorded study, clearly bounded

“Our historical dataset contains 40 recorded repair episodes from one local
model, qwen3:4b, across five selected task families. The families include
cryptographic mistakes and web security problems. This is an exploratory
dataset. The runs are recorded and auditable, but they are not a random sample
of all AI coding tasks.”

**Source:** [README, Current result](../README.md).

## Slide 5 — The finding

“Focus on the 20 historical episodes labeled nominally unavailable. In nine
of them, the final candidate passed the implemented family tests yet the
benchmark rejected it. The colored dots represent those nine discordant
finals. This is a result about these selected runs and this evaluator; it is
not a population error rate or a security certification of the code.”

**Source:** [archive-based recount](../docs/MEASUREMENT_FOLLOWUP_20261030.md),
[paper Results](../paper/final.md).

## Slide 6 — The second gate

“The final acceptance rule used two pieces: a pass on the implemented family
tests *and* a condition flag. The flag was false in the nominally unavailable
condition. That is why some code could pass tests and still get a final fail.
The agent was not shown this hidden rule. The implemented tests are finite,
so we cannot claim those nine candidates were generally secure.”

**Source:** [paper Results and Discussion](../paper/final.md).

## Slide 7 — We checked the evidence from several angles

“We did more than spot one odd verdict. We rebuilt the historical counts from
saved receipts and put automated checks in the public repository. We authored
a broader catalog of 20 finite task families and rechecked 1,820 designed
candidate-and-condition decisions against independent reference code. Those
designed candidates were *not* AI outputs. Separately, a corrected-oracle
feasibility pilot completed 30 episodes in two authored families. Human review
of the catalog is still pending.”

**Sources:** [measurement follow-up](../docs/MEASUREMENT_FOLLOWUP_20261030.md),
[corrected pilot](../docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md),
[README](../README.md).

## Slide 8 — A clear result, with clear limits

“The firm conclusion is that this checker’s implemented tests and final
verdict disagreed in nine archived finals. We do not yet know whether wrong
feedback generally causes an AI to keep editing or make code worse. The
historical intermediate logs have a key gap: none of 81 action receipts
contains the raw family-test result. That means we cannot reconstruct every
moment when an intermediate candidate might have passed the tests.”

**Source:** [paper Results and limitations](../paper/final.md).

## Slide 9 — Same code, two verdicts

“Our planned experiment will start from an agent-generated candidate verified
by an independent bounded oracle. We will save the code and prior transcript,
then branch the same state. One branch sees a truthful `PASS`; the other sees
a false `FAIL`. We will compare stopping and whether the final candidate still
satisfies the finite security property. We have one selected excluded pilot
pair, which motivates the question but does not establish a general effect.
The prospective main study has no eligible results yet.”

**Source:** [integrated extension](../docs/INTEGRATED_STUDY_EXTENSION_20261018.md),
[selected excluded pair](../docs/EXCLUDED_V7_R1_C5_PAIRED_CASE_20261018.md).

## Slide 10 — Before judging the AI, check the judge

“The historical audit is complete and reproducible. The next research stage
requires independent review of tasks and oracles, a frozen protocol, and a
safe full run. The main release gate currently passes zero of twelve checks,
and there are zero eligible main episodes. Our central lesson so far is
simple: before interpreting an AI’s reaction to feedback, verify that the
feedback measures what it claims to measure.”

**Sources:** [README, status](../README.md),
[main release gate](../docs/MAIN_RELEASE_GATE_MATRIX_20261005.md).

## If someone asks

**“Were the nine fixes actually secure?”**

We know they passed the benchmark’s implemented family tests. We do not know
that they were secure against every relevant attack or use case.

**“Did false feedback make the AI worse?”**

The 40 historical episodes cannot establish that. One selected excluded pilot
pair suggests a question for a properly matched prospective experiment.

**“Why not just run hundreds of episodes now?”**

The main study must first pass task, oracle, logging, safety, analysis, and
independent-review checks. A larger sample would not correct invalid labels.

**“Can I inspect the evidence?”**

Yes: [public repository](https://github.com/Imranqsl212/AiResearch),
including archived analyses, checks, the draft paper, and the prospective
release-gate status.
