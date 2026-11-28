# Freely written expressions after seeing a program run

This exploratory comparison follows the CPython and dateutil edit-menu experiments. It tests whether requiring the model to author a replacement changes what we observe on a small, externally published benchmark. We know the prior projects’ outcomes. We freeze these new tasks, source, held-out domains, clock cutoff, prompt hashes and schedule before collecting any response. No human case admission or repository-scale repair is claimed.

## Cases and calibration

We selected four distinct QuixBugs Python cases with (1) a one-expression difference between the upstream faulty and repaired source, (2) a small scalar expression at that location using integer or Boolean operations, (3) a compact complete finite grading domain, and (4) independently implementable semantics. This purposive selection is neither random nor exhaustive. QuixBugs is a challenge corpus rather than a catalogue of production incidents. The model may previously have encountered these algorithms. Both the faulty upstream program and its supplied working correction are eligible starts. [Primary benchmark and pinned sources](https://github.com/jkoppel/QuixBugs/tree/4257f44b0ff1181dedaedee6a447e133219fcebf)

| Task | Independent grading domain | Current-program shared input | Current-program revealing input |
| --- | --- | --- | --- |
| Maximum contiguous sublist sum | Every list of length 0–4 over −2, 0, 3 (121) | [7, −2, 1] | [−7, 4, 3] |
| Balanced parentheses | Every parenthesis string of length 0–5 (63) | (()())() | (()(() |
| 0–1 knapsack | Capacities 0–5 with 0–3 ordered items from (1,1), (2,4), (3,3) (240) | Capacity 8 with (2,5), (3,7) | Capacity 7 with (3,8), (4,11) |
| Quicksort retaining duplicate items | Every list of length 0–4 over −2, 0, 3 (121) | [8, −2, 5] | [8, −2, 8] |

Each shared input gives exactly the same output on upstream working and faulty programs. Every revealing input distinguishes them. The model sees one of these actual program executions or sees no execution. The task contract, source, indicated editable expression and one-turn editing budget stay fixed within model-by-start blocks. Neither expected output nor pass/fail is supplied. The expression location is identified in both faulty and working code. We do not ask models to localize bugs.

The response is keep or one replacement expression written by the agent. No menu of repair candidates is displayed. The maximum is 200 ASCII characters, 64 abstract-syntax-tree nodes, constant magnitude 1,000 and intermediate magnitude 1,000,000. The text interpreter implements arithmetic, comparisons, conditionals, Boolean connectives, absolute value, minimum and maximum over declared scalar local variables. Model text is never passed to Python execution. The surrounding fixed algorithm is replayed on an independent enumerated domain; brute-force interval sums and packing, deletion of adjacent matching parentheses and built-in sorting define the expected results. The probes and held-out domains are disjoint.

## Allocation and endpoints

Use the two previous hosted model aliases at low requested reasoning effort. There are 16 matched blocks (4 tasks × 2 starts × 2 models) with 3 independent fresh sessions per block, 48 calls if fully observed. Four shuffled waves each cover all four tasks and all four model-by-start combinations once. Seed 2026112804 fixes assignments and order. The planned primary contrast is revealing output versus no output, paired by model and starting source, with repair (from faulty starts) and preservation (from working starts) reported separately. Also report all three arms and explicit replacements, with the number of passing submitted expressions whose parsed syntax differs from the upstream correction. Different syntax does not itself imply a different algorithm. A pass requires all the held-out cases for that task. These four tasks share one published benchmark. Model comparisons do not create extra distinct defects.

Keep malformed replies, unsupported expressions, provider failures and unstarted rows distinct. Report scored counts, scheduled denominators and missing paired endpoints. An answer in the valid expression language that fails to execute on a held-out case fails that case. Replay all private native captures before export. No retry, replacement model, paid API or spillover into the next quota window. Serial hosted subscription calls require the same window (reset Unix 1795890789), ordinary usage allowed, a current quota below 100%, and sufficient time to finish before reset. Close the study with all scheduled missing rows if the window, account, consent or connectivity ends.
