# Nine more historical code pairs have comparable visible AST projections

**Excluded post hoc audit, 4 November 2026.** The sealed 40-run historical
archive contains 77 logged Python submissions. The earlier source-fidelity
audit parsed 63 exactly as logged, found 11 with an unquoted logger
`<REDACTED>` marker, and found three with other syntax errors. Quoting the
marker makes all 11 marked strings parseable. This produces a **fictitious
surrogate AST**, not the original expression or the AST of executed code.

The [new read-only recount](logged_source_surrogate_ast_20261104.py) verifies
all sealed log and receipt hashes through the earlier audit, joins each source
to its logged SHA-256, and substitutes a quoted placeholder only for the 11
strings with one marker in an assignment. Its
[JSON result](logged_source_surrogate_ast_20261104.json) contains no source
text. It compares adjacent submissions inside episodes:

| Adjacent-pair evidence | Pairs | AST differs in visible projection | Visible called-API inventories differ |
| --- | ---: | ---: | ---: |
| Both logged sources parse exactly | 25 | 25 | 17 |
| At least one needs a placeholder | **9** | **9** | **4** |
| Other syntax error prevents comparison | 3 | Unknown | Unknown |
| **Total** | **37** | **34 observed projection differences** | — |

Thus 9 of the 12 pairs previously outside the exact-AST subset have a
detectable difference in their **visible logged projection**. This does not
show that the nine revisions improved security, changed strategy, or changed
the original redacted expression. The placeholder can hide calls, literals,
and entire expressions; equality or difference in the projected API inventory
is not an exact inventory of executed calls. The three remaining pairs are
unparseable even under this limited procedure. The archived executed-source
hashes differ from these redacted logged strings, so **zero executed ASTs are
recovered** by quoting markers.

Reproduce without running the model or any candidate code:

```sh
python3 -B -m analysis.logged_source_surrogate_ast_20261104 --check
python3 -B -m unittest -q tests.test_logged_source_surrogate_ast_20261104
```
