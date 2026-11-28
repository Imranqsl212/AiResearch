# What the same test command establishes in a public trace

All ten issues were reserved in both archives before the earlier audit. Counts refer to episodes, using the first and last invocation of each identical admitted command. Two SWE-agent trace files were unavailable. An exit code and a test-suite verdict have separate definitions.

| Archive | Reserved | Trace available | Admitted command | Exact repeat | Two formal verdicts | Formal fail to pass | Nonzero to zero exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SWE-agent | 10 | 8 | 5 | 4 | 0 | 0 | unassessed |
| OpenHands | 10 | 10 | 2 | 0 | 0 | 0 | 0 |

## Witnesses

No command met either transition rule.

A repeated command can run a changed script or cover a different set of tests. A process can also exit successfully after printing a wrong answer. Positive rows locate observations in the public trace. They cannot establish that feedback caused the next edit.

Rebuild from hash-matched public traces with `python3 -B -m analysis.swe_recheck --fetch`. The default command uses the local cache. To recount from the released per-command ledger, use `--recount`.
