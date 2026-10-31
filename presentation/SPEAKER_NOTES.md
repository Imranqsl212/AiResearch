# Research talk — simple speaker notes

**Deck:** [PowerPoint](Research_Update_2026-11-01.pptx)

**Audience:** people new to AI and cybersecurity

**Time:** about 5–6 minutes
**Presenter:** Imran Zakirov

Read [START_HERE.md](START_HERE.md) first. The notes are also embedded in the
PowerPoint. Speak naturally; you do not need to read these words exactly.

## 1. Our tests said PASS. Our grader said FAIL.

“We watched an AI try to fix small safety problems in code. In some runs, its
final code passed the tests **we had written**, but our checker still gave a
final FAIL. Today I will show how that happened and what it means.”

**Source:** [repository overview](../README.md), [paper](../paper/final.md).

## 2. What was the AI doing?

“The AI saw a small code problem and suggested a fix. Our software checked it
and sent back PASS or FAIL. The AI could stop or try another fix. We recorded
what happened in each run.” This is revision within a session; the model was
not trained during the study.

**Source:** [paper Methods](../paper/final.md).

## 3. A teacher checks every box...

“Imagine the teacher's checklist marks every listed item correct, but an extra
rule still gives the answer FAIL. Our checker had a rule like that. A checklist
can miss things, so a pass on the listed checks does not mean the answer is
perfect.”

**Source:** Analogy based on [paper Results](../paper/final.md).

## 4. Nine times, tests and score disagreed

“We reviewed **40 recorded runs** from one local AI across five kinds of small
security tasks. Twenty were put in a group our experiment called
‘unavailable.’ In **nine of those twenty**, the final code passed our written
tests, yet the final score was FAIL. The colored dots show those nine.” These
counts describe this selected study, not all AI coders.

**Sources:** [archived count check](../docs/MEASUREMENT_FOLLOWUP_20261030.md),
[paper Results](../paper/final.md).

## 5. Our checker had an extra rule

“**We**, the researchers, added a hidden no-accept rule to that group. When
the rule said no, our checker produced FAIL even if its own written tests
passed. The AI did not see this rule.” This was a design choice in our local
experiment; it did not prove that the task truly had no possible fix.

**Sources:** [paper Results](../paper/final.md),
[project overview](../docs/PROJECT_OVERVIEW_20261029.md).

## 6. The score can mislead us

“If we looked only at the final FAIL, we might say the AI failed or kept
trying too long. Our records show the tests and score disagreed. So that
score cannot tell us whether the AI knew when to stop.” The old logs did not
save the underlying result for any of 81 intermediate checks. Passing our
small tests also does not prove full security.

**Source:** [paper limitations](../paper/final.md).

## 7. What we have done so far

“We checked the old records again and made the result repeatable from saved
files. We drafted 20 kinds of small security tasks, which still need human
review. We ran 30 **separate practice runs** with a revised checker. We
shared the code and analyses publicly.” The 30 practice runs are separate
from the 40 old runs and from the planned larger experiment.

**Sources:** [README](../README.md),
[measurement follow-up](../docs/MEASUREMENT_FOLLOWUP_20261030.md),
[practice pilot](../docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md).

## 8. Same code. Two different messages.

“Our next experiment will save the exact same code and AI history, then
continue two copies. One hears a true PASS; the other hears a false FAIL. We
will compare what each does next and whether the final code still meets the
specific check. **This is planned; it has no accepted main results yet.**
Before judging the AI, check the grader.”

As of 1 November 2026, the proposed main study has zero eligible runs and its
12-point release check remains closed.

**Sources:** [study extension](../docs/INTEGRATED_STUDY_EXTENSION_20261018.md),
[current status](../README.md).

## Three likely questions

**Were the nine fixes completely safe?** No. They passed the small written
tests; we did not prove complete safety.

**Did the wrong message make the AI worse?** The old runs cannot answer that.
The two-message comparison is our planned next experiment.

**Who made the extra rule?** Our research team put it in the local checker;
the AI did not see it.
