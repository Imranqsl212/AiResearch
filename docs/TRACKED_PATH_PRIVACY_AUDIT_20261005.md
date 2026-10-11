# Tracked path privacy audit — 5 October 2026

This is a **release review worklist**, not privacy approval. A byte scan of
`git ls-files` for the literal local home-path prefix found **54 occurrences in
10 tracked files** after ordinary README and Markdown examples were made
relative or generic. The scan does not inspect Git history or identify other
personal information, provider text, credentials, or free-text disclosures.

| Tracked file group | Files | Literal occurrences | Disposition |
| --- | ---: | ---: | --- |
| Historical RAG analysis JSON | 2 | 5 | Preserve current evidence; create a reviewed public copy or exclude it from a release. |
| Real-code calibration JSON | 5 | 44 | Preserve current evidence; source-log paths require review and a release-specific mapping. |
| Candidate runtime safety probe source | 1 | 1 | A host-specific path is embedded in the current Docker image; changing it requires a new image and safety receipt. |
| Saved safety result JSON | 2 | 4 | Preserve the recorded receipt; a public release copy must not silently rewrite an attested result. |

The files are `analysis/excluded_cross_model_rag_report_20261004.json`,
`analysis/excluded_rag_block_report_20261004.json`, the five
`benchmark/real_code_*calibration*.json` files,
`sandbox/images/candidate_runtime.py`, and the two JSON receipts under
`sandbox/safety_checks/`. The historical reports and safety receipts were not
modified by this audit. A filtered submission package can omit unrelated
calibration/RAG/safety records if the chosen journal's supplement does not use
them; a public repository release needs a separately reviewed plan for tracked
files and history.

The [historical paper's raw archive review](../paper/SANITIZED_REVIEW_CANDIDATE_20261005.md)
is a different, larger privacy task. Its sanitized candidate has table-only
replay but no human release approval. Neither this tracked-file scan nor that
replay authorizes publication of raw traces.
