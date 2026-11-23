# Author-review manuscript bundle — v20, 23 November 2026

The [v20 archive](../experiments/runs/paper_author_review_manuscript_20261123_v20.tar.gz)
is a filtered **REVIEW_ONLY** snapshot of the current numbered manuscript,
its identified and anonymous PDF/DOCX renderings, and selected supporting
results. Its **116 members** comprise 114 exact source files,
`REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`. The
[receipt](../experiments/runs/paper_author_review_manuscript_20261123_v20.tar.receipt.json)
records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v20 archive (3,337,234 bytes) | `90d9cf11a5ed0e9c92328d187b908482234c2a6f70d23dacfbd1beaac9a48f52` |
| Internal source-hash manifest | `dac5e10d8c262e93ac807797fccd01dee7ed7db2ac714c7b5dc4a95a8e9361bc` |
| Current numbered manuscript | `87a0f4a5254f56a825f50509f1972c945373167eefdf38c8972be904f547caf3` |

Compared with [v19](AUTHOR_REVIEW_BUNDLE_V19_20261104.md), this snapshot
refreshes the manuscript and four main renderings, updates their bindings in
the [pending author decision record](AUTHOR_SUBMISSION_DECISIONS_20261005.md),
and adds seven selected files:

- The discovery audit's `external_audit_20261122/summary.json`.
- The follow-up package's `README.md` and main `summary.json`.
- The OpenHands coverage `openhands/summary.json`.
- The projection control's `results.json`, `execution_receipt.json`, and `REPORT.md`.

The [full follow-up reproduction package](../submission_audit_20261123/README.md)
contains the additional protocols, scripts, per-issue records and verification
instructions. This manuscript archive includes selected results rather than
that complete package. The projection result contains explicitly simulated
completion payloads; it reports no executed agent runs. No raw public
trajectories, empirical model request/response payloads, cache files or
additional run archives were added. The older author-year adaptation remains
included as a separately labeled working draft.

The builder verified the allowlist, exact source hashes, author-decision
bindings, receipt and limited host-path screen. A deterministic rebuild
produced the same archive bytes. All 19 earlier archives and their receipts
were preserved byte for byte. Historical snapshots can be verified with
`--no-local-compare` after their source files change.

The current abstract has 233 space-delimited words, excluding keywords.
Both main PDFs have 18 A4 pages locally, and the current anonymous PDF/DOCX
pair passed the automated author-identifier and metadata screen. The v20
remote Linux recheck remains pending. Human author approval, scientific
sign-off, task admission, privacy clearance and a journal data route remain
pending. The bundle's `related_data_public_git_revision` remains **null**;
the receipt does not attest a final source revision or authorize submission.
The identified decision form must not accompany anonymous peer review.

From the repository root:

```sh
python3 -B -m paper.build_author_review_bundle verify --bundle-version v20
python3 -B -m paper.build_author_review_bundle verify --bundle-version v19 --no-local-compare
python3 -B -m unittest -q paper.test_author_review_bundle
```
