# Natural false alarms from upstream repositories

Four candidate cases from three projects have pinned parent and fix revisions, a source-only parent archive, an unchanged implementation, and a local before/after comparison. The selection was purposive. No agent ran these tasks. Two independent human decisions per case remain outstanding.

| Case | What the checker got wrong | What was replayed here |
| --- | --- | --- |
| 01. CPython process hashes | A fixed environment seed is supposed to reproduce a hash. The old test expected separate processes to produce different hashes. | Both historical test method bodies ran on the installed interpreter. The launcher exercised the environment-inheriting and isolated branches. With a fixed inherited seed the parent failed and the fix passed. Both passed with isolated children. Historical interpreter builds were not recreated. [Commit and parent](https://github.com/python/cpython/commit/220ba72c20869975ee9e900f78c7a724db13a3ee) · [Parent specification](https://github.com/python/cpython/blob/4cb6d37d1d9b2463a121f5f0c6ed9aed2d3f2f9a/Doc/using/cmdline.rst) |
| 02. CPython pretty-printing | A test hard-coded one order for two incomparable tuple keys. The parent formatter used object identity to break the tie. Both printed representations reconstruct the same mapping. | The original formatter ran on both allocation orders. The old equality assertion rejected one order. The revised assertion accepted both. The replay controls the input allocation and uses the two assertion predicates. [Commit and parent](https://github.com/python/cpython/commit/0fd1062a7639f2a155fd6d04eb9cebbd4e5118df) · [Parent formatter](https://github.com/python/cpython/blob/6a01fc5d4114ac56105ecbfb4ae3cbe043818449/Lib/pprint.py) |
| 03. pandas logarithmic ticks | The plotting test demanded exact floating-point equality for visually equivalent tick locations. The maintainers replaced it with a tolerant comparison. | Both upstream test bodies received identical, one-ULP-offset or plainly wrong tick positions. Only the one-ULP input changed from FAIL to PASS. This is a constructed assertion-level witness. We did not reproduce the reported Linux rendering stack. A related test in the parent already contains a tolerance, a potential source of clues in a behavioral study. [Maintainer PR](https://github.com/pandas-dev/pandas/pull/64385) · [Earlier discussion](https://github.com/pandas-dev/pandas/pull/64317) |
| 04. python-dateutil repeated local time | At the autumn clock change, an ISO string includes the UTC offset but loses the named zone. Python deliberately treats comparisons across different zones as unequal in the ambiguous hour. The old property rejected a parse that preserved the wall time and offset. | The parent parser ran at 03:00 and at both occurrences of 01:00 in US/Eastern. The old body failed at both 01:00s and passed at 03:00. The revised body passed at all three. The entire decorated upstream property passed under a fixed Hypothesis seed at both revisions. Adding the reported inputs to each property exposed the old failure. This last distinction matters when a random test appears green. [Merged fix](https://github.com/dateutil/dateutil/pull/1581) · [PEP 495](https://peps.python.org/pep-0495/#aware-datetime-equality-comparison) |

## Scope and selection

The [selection rule](selection.md) was written before searching this session. The [source manifest](sources.json) binds its digest, exact parent and fix, complete changed-file lists, relevant test/implementation/specification file hashes and the downloaded parent archives. The searched repositories were CPython, pandas, NumPy and python-dateutil. The searches used GitHub issue and commit search for terms including leap day/year, hash randomization, dictionary order, flaky tests, time of day and precision. We read the parent diff to distinguish changes to the test from changes to the product.

Other inspected candidates included CPython issue 58365 (parser semantics were disputed), the CPython GDB hash-randomization change (overlapping seed mechanism and additional debugger environment), NumPy PR 8656 (skips the affected check on certain platforms) and NumPy PR 27009 (raises a tolerance from four to five spacings without an independent admissible error threshold). pandas PR 64317 was treated as related evidence for case 03. Calendar search results associated with product fixes or new date functionality were outside the sampling rule. This screen establishes no population frequency. The [replay receipt](replay_results.json) records measured method-level results and tool versions.

## Reproduce

The source checker has only standard-library dependencies. Fetching uses the GitHub CLI. Existing downloads can be verified offline. The pandas witness requires NumPy and pandas; the parser witness uses the pinned parent dateutil source, six and system zone data. The optional complete property test additionally requires Hypothesis and pytest. See the receipt for the versions used. Run one replay case per process so package imports remain isolated.

```sh
export CASE_CACHE=.local_private/c5_external_20261124
python3 -B external_checker_audit_20261124/cases.py --cache "$CASE_CACHE" --fetch
python3 -B external_checker_audit_20261124/replay.py --cache "$CASE_CACHE" --case seed
python3 -B external_checker_audit_20261124/replay.py --cache "$CASE_CACHE" --case order
python3 -B external_checker_audit_20261124/replay.py --cache "$CASE_CACHE" --case plot
python3 -B external_checker_audit_20261124/replay.py --cache "$CASE_CACHE" --case fold
python3 -B external_checker_audit_20261124/replay.py --cache "$CASE_CACHE" --case fold --upstream
python3 -B external_checker_audit_20261124/cases.py --cache "$CASE_CACHE" --packets /private/tmp/new-parent-only-packets
```

## Review and agent access

Each human reviewer independently checks the public contract, test-only diff, reproducible trigger and possible alternative interpretation. Each completes a separate copy of [the review form](review_template.csv) before seeing the other review. A disagreement remains open until adjudication; unfilled forms express no opinion.

Only after admission, give an agent the contents of its own neutral packet: the parent source archive and TASK.md. Supply a fresh workspace without future Git history, external network access or access to these investigator materials. The preparer verifies every relevant parent file against the archived snapshot. Each project retains its original license. These public historical cases can occur in model training data; source isolation does not establish novelty to the model.
