# Historical source fidelity audit (exploratory cohort)

This is a **post hoc, descriptive audit** of the existing 40-episode main exploratory cohort `rag-overnight-v2-main-0-5-0`. It does not change the original trajectories, archived bytes, or the denominators in the manuscript. The machine-readable [source and adjacent-pair inventory](../analysis/source_fidelity_v1.json) contains IDs, syntax categories, hashes, and structural indicators, with no candidate source text. Rebuild it with `python3 -B -m analysis.source_fidelity_v1`; verify the saved report with `python3 -B -m analysis.source_fidelity_v1 --check`.

## Finding and mechanism

| Logged Python sources | Count | Evidence |
|---|---:|---|
| Parseable as logged | 63 | `ast.parse` on the exact logged source succeeds. |
| Syntax error with `<REDACTED>` marker | 11 | Each marker occurs in an assignment matching the historical trajectory logger's credential-assignment redaction pattern. The logger replaced the expression with the unquoted token `<REDACTED>`, which is invalid Python syntax. These sources span slots 000003, 000021, and 000022. |
| Syntax error without marker: compound `def` after semicolon | 2 | Slots 000018 steps 2 and 3 contain a compound function definition after a semicolon on the same line. |
| Syntax error without marker: unmatched brace | 1 | Slot 000008 step 3 has an extra closing brace. |
| **Total** | **77** | All `attempt` tool calls in the 40 sealed logs. |

The [trajectory logger](../experiments/trajectory_logger.py) in the study source revision recursively sanitized strings in `parameters`, `action`, and `raw_action` before writing JSONL. The same redacted text appears in the corresponding `TOOL_OBSERVATION` events. A harmless demonstration is that `token = bytes(range(16))` becomes `token=<REDACTED>`; the latter cannot be parsed. This redaction behavior is confirmed in the study commit `98a4dcf414672c1725e4acdb9f08045370aa7f64` (`experiments/trajectory_logger.py`).

The sealed archive's 40 JSONL files are byte-identical to the run logs. It therefore preserves the *already redacted* source, rather than an unredacted original. The final evaluator receipts retain only a SHA-256 digest of executed source. In slots 000003 and 000022, that digest differs from the final logged-source digest; both logged final sources contain a marker. A hash cannot restore the erased expression. The episode workspaces use temporary directories and do not form a retained source archive. No recoverable complete original for the 11 marker cases was found in the audited artifacts; an external backup, if any, was not examined.

Substituting a fictitious quoted literal for `<REDACTED>` makes all 11 marked strings parse, which confirms that the marker is the immediate syntax obstacle. Such substitution **does not recover the executed code or its AST**: the erased expression may have been a call, constant, or more complex expression. The three unmarked strings remain syntax errors and cannot have a Python AST as submitted. Accordingly, “AST for all 77 attempts” is not an attainable result from these records.

## Adjacent source comparisons

There are 37 within-episode adjacent pairs. Both exact logged strings parse in 25 pairs. Within those 25, zero normalized ASTs are identical, and 17 pairs change their called-API inventory. None of the 37 logged pairs is byte-identical. The remaining 12 pairs lack one or both logged ASTs. These are descriptive features of the logged strings, not a measured security-strategy switch rate. Because redaction changes source bytes and sometimes syntax, comparisons involving the 11 marked strings should not be promoted to exact executed-source comparisons.

For a future run, preserve a restricted, write-once original source artifact *before* redaction, link it to the submitted action and evaluator receipt with a content hash, and separately produce a privacy-reviewed public projection. Record AST or code-structure summaries from the original only after checking whether they leak secrets. Existing historical records must remain unchanged; any newly recovered external originals need a separate versioned provenance trail and analysis.
