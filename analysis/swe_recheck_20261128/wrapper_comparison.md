# Post-hoc sensitivity to working-directory prefixes

All ten issues were reserved in both archives before the earlier audit. Counts refer to episodes, using the first and last invocation of each identical admitted command. Two SWE-agent trace files were unavailable. An exit code and a test-suite verdict have separate definitions. This sensitivity also admits a literal directory change followed by a single eligible invocation. The directory remains part of the full command identity.

| Archive | Reserved | Trace available | Admitted command | Exact repeat | Two formal verdicts | Formal fail to pass | Nonzero to zero exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SWE-agent | 10 | 8 | 5 | 4 | 0 | 0 | unassessed |
| OpenHands | 10 | 10 | 5 | 4 | 0 | 0 | 1 |

## Witnesses

| Archive / issue | Change observed | Benchmark resolved | First output locator | Last output locator |
| --- | --- | --- | --- | --- |
| B / matplotlib__matplotlib-25479 | process nonzero to zero | False | /7/content | /27/content |

A repeated command can run a changed script or cover a different set of tests. A process can also exit successfully after printing a wrong answer. Positive rows locate observations in the public trace. They cannot establish that feedback caused the next edit.

Rebuild from hash-matched public traces with `python3 -B -m analysis.swe_recheck --allow-cd --fetch`. The default command uses the local cache. To recount from the released per-command ledger, use `--allow-cd --recount`.
