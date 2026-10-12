# Local author-review manuscript bundle — corrected v8, 12 October 2026

**Status: REVIEW_ONLY.** This is a filtered handoff for author inspection, not a journal supplement or submitted manuscript. The raw experiment artifacts are tracked separately in the public repository.

The current [v8 archive](../experiments/runs/paper_author_review_manuscript_20261012_v8.tar.gz) contains 37 members: 35 exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`. The source files include `paper/final.md`, identified and anonymous PDF/DOCX copies, six figures, `paper/references.bib`, eight historical derived CSV tables, `paper/artifacts/results.json`, the source-fidelity inventory, separate v7 episode and fork audit JSON files, the strategy-coding protocol, the v7 pilot report, the cover-letter template, data-availability options, and the author decision form. The independent transformed-receipt recount and separate local original-byte audit each have their script, focused tests, and methods note in the package. Every source file is copied byte for byte and listed with its SHA-256 and size in the internal manifest. The v7 audits are separate from the historical results and are not pooled with the 40-episode denominator. The archived derived tables preserve earlier exploratory calculations even where the corrected manuscript no longer discusses them.

| Receipt item | SHA-256 |
| --- | --- |
| v8 review archive | `b4c082c9ee0a92ec5185b94e1d759ab1d40d0dd55da74176dc1fb2a5211e0077` |
| v8 internal source-hash manifest | `53313349e15c183178c82163edcaf0825d01564e06d87c646d09a9475a38dc06` |
| Identified PDF | `d41b536071595f208e4eaabf725cf6db7d8d2f762fb42cf78d06724bad89c336` |
| Identified DOCX | `fbbf1130c3ebe4fc9044dd03bb7ad5d6c21960bfab1850afee247b4536ce3787` |
| Anonymous PDF | `32baf373bbf1696eda9bec80feaecb2f0a70f5cb05a748165e3d9aaa8d84cd08` |
| Anonymous DOCX | `a4ebc3dcb4967e4a64a0326bfdaf3b9557514f1eb8fc26c9ec7969d5c93ed5e1` |

The adjacent tracked [v8 receipt](../experiments/runs/paper_author_review_manuscript_20261012_v8.tar.receipt.json) records the archive and manifest hashes. The builder uses fixed archive metadata and gzip timestamps. Two independent builds produce identical archive bytes in the local test. A SHA-256 receipt detects accidental changes when compared with a trusted copy; it is not a signature or independent timestamp. The older [v1](../experiments/runs/paper_author_review_manuscript_20261005_v1.tar.gz), [v2](../experiments/runs/paper_author_review_manuscript_20261005_v2.tar.gz), [v3](../experiments/runs/paper_author_review_manuscript_20261005_v3.tar.gz), [v4](../experiments/runs/paper_author_review_manuscript_20261005_v4.tar.gz), [v5](../experiments/runs/paper_author_review_manuscript_20261008_v5.tar.gz), [v6](../experiments/runs/paper_author_review_manuscript_20261008_v6.tar.gz), and [v7](../experiments/runs/paper_author_review_manuscript_20261012_v7.tar.gz) archives remain untouched and verify without comparing to the edited workspace. V2 holds the previous 14-page, three-table draft. V3 predates the final recomputation of its historical input-hash ledger. The updated ledger in v4–v8 has SHA-256 `9da89378d1f9b769f5fdc5597ba1dcf666c8453aea53363d9f2d46eea31ccdb0`. V5 updates the AI-use disclosure and adds the independent transformed-receipt recount. V6 adds a read-only original-byte audit. V7 updated the data-availability wording before these scientific corrections. V8 includes the corrected manuscript, rendered files, and public-data-revision wording. The historical packaging ledger bytes are absent, and one digest in the current tracked input ledger differs from the archived inventory; see the [audit note](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md).

The filtered package excludes original trajectories, candidate source, model responses, source snapshots, the unredacted original archive, the sanitized review candidate, and unrelated historical JSON. `paper/artifacts/input_hashes.csv` lists historical source hashes, but the hashed raw inputs are not in this package. The tracked v7 audit JSON files also need the separately tracked pilot traces for replay. The included audit scripts require those separate archives; this bundle alone cannot independently regenerate reported numbers from raw logs. It reflects the exploratory paper and an excluded feasibility pilot, not the proposed prospective main study.

The builder screens selected bytes and expanded DOCX members for local home-path/account markers, with zero matches in this package. That limited screen does **not** establish privacy clearance for all metadata, images, or free text. The source tree has other tracked files with local paths. This filtered archive has not been approved as a journal supplement, regardless of the GitHub visibility of the experiment artifacts.

To verify the archive and compare its copies with the current workspace:

```sh
python3 -B -m paper.build_author_review_bundle verify \
  --archive experiments/runs/paper_author_review_manuscript_20261012_v8.tar.gz
```

If the manuscript, form, figures, or tables change, make a new versioned package; do not overwrite this receipt. Authors still need to approve the exact claims and limitations, author metadata and declarations, data-access route, privacy disposition, and venue-specific files using [the decision form](AUTHOR_SUBMISSION_DECISIONS_20261005.md).
