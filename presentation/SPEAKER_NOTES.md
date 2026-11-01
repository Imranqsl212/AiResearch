# Two-minute research talk — speaker notes

**Deck:** [PowerPoint](Research_Update_2026-11-01.pptx) · [PDF](Research_Update_2026-11-01.pdf)

**Audience:** people new to AI and cybersecurity

**Presenter:** Imran Zakirov

Speak slowly, about 15–20 seconds per slide. The notes are also embedded in
the PowerPoint. Read [START_HERE.md](START_HERE.md) before practicing.

## 1. Our tests said PASS. Our grader said FAIL.

“We asked an AI coder to repair small security problems. In some saved runs,
its final code passed the checks we wrote, yet our final grader said FAIL.
How can both be true?”

## 2. What was the AI doing?

“Think of a student solving a coding exercise. The AI sees a problem, writes
a fix, receives PASS or FAIL from our checker, then either stops or tries
again. This is one session; we did not retrain the AI.”

## 3. Nine times, tests and score disagreed

“We examined 40 old runs. Twenty had an extra acceptance rule. In nine of
those twenty, the **final** code passed the written tests, but the final
decision was FAIL. These are counts from our selected local study.”

## 4. One real run: a one-time encryption value

“In one saved run, the AI was repairing code that creates a one-time value for
encryption, called a nonce. Its final code passed our small nonce tests. Our
hidden ‘never accept’ rule still returned FAIL. We added that rule; the AI
could not see it. A test pass does **not** prove this code fully secure.”

## 5. The score can mislead us

“We therefore cannot use that final FAIL alone to claim the AI should have
stopped trying. We also cannot call the code fully secure: our tests covered
only a few cases. The old logs lack raw results for intermediate checks.”

## 6. Same code. Two different messages.

“Our fairer comparison starts with the same checked code and history. One
copy hears true PASS; another hears false FAIL. We then compare their next
steps. We have audited 40 old runs, drafted 20 new task types, and run small
exploratory pairs. The main study still needs independent task review and has
zero accepted runs. Our lesson so far is:
**check the grader before judging the AI.**”

## If someone asks

**Was the AI's code actually safe?** We know only that nine final submissions
passed the small tests. We did not prove complete security.

**Did the false FAIL make the AI worse?** The historical 40 runs do not answer
that. Small excluded paired pilots are exploratory; the main study has not
started.

**Who made the hidden rule?** The research team put it in its local checker.
It was a design flaw for measuring whether a task was truly impossible.

**Evidence:** [paper](../paper/final.md),
[measurement audit](../docs/MEASUREMENT_FOLLOWUP_20261030.md),
[main-study status](../README.md).
