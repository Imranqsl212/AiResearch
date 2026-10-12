# Local author-review manuscript bundle — updated 12 October 2026

**Status: REVIEW_ONLY.** This is a filtered handoff for author inspection, not a journal supplement or submitted manuscript. The raw experiment artifacts are tracked separately in the current research branch.

The current [v7 archive](../experiments/runs/paper_author_review_manuscript_20261012_v7.tar.gz) contains 37 members: 35 exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`. The source files include `paper/final.md`, identified and anonymous PDF/DOCX copies, six figures, `paper/references.bib`, eight historical derived CSV tables, `paper/artifacts/results.json`, the source-fidelity inventory, separate v7 episode and fork audit JSON files, the strategy-coding protocol, the v7 pilot report, the cover-letter template, data-availability options, and the author decision form. The independent transformed-receipt recount and separate local original-byte audit each have their script, focused tests, and methods note in the package. Every source file is copied byte for byte and listed with its SHA-256 and size in the internal manifest. The v7 audits are separate from the historical results and are not pooled with the 40-episode denominator.

| Receipt item | SHA-256 |
| --- | --- |
| v7 review archive | `8b35ebc07b4a4b99c6eb99a66c1a4488b3b6e3273bf0103548a092fe57e73baf` |
| v7 internal source-hash manifest | `b8fcd3207cb928b75fa8123aa8c0ee9652fc98cf3f0b2adf64148541ab5c7fbe` |
| Identified PDF | `b5bf09f7348ec047422f134bd0c173980df3e79f8c2426ed2f91269f62d8152e` |
| Identified DOCX | `48d75e5aac1cbd777debacc9f55994f61a5a2aeb4e4a06cf72dbf6fd90c206df` |
| Anonymous PDF | `1791c59d6c44e3c3263a9d987377a0cb6eae1c17b1ecd72de77830e8fae11391` |
| Anonymous DOCX | `43530e9b662f177bdcb1c1e34d6b772b8f1f469323a3ca343dc1b70fe3d289e3` |

The adjacent tracked [v7 receipt](../experiments/runs/paper_author_review_manuscript_20261012_v7.tar.receipt.json) records the archive and manifest hashes. The builder uses fixed archive metadata and gzip timestamps. Two independent builds produce identical archive bytes in the local test. A SHA-256 receipt detects accidental changes when compared with a trusted copy; it is not a signature or independent timestamp. The older [v1](../experiments/runs/paper_author_review_manuscript_20261005_v1.tar.gz), [v2](../experiments/runs/paper_author_review_manuscript_20261005_v2.tar.gz), [v3](../experiments/runs/paper_author_review_manuscript_20261005_v3.tar.gz), [v4](../experiments/runs/paper_author_review_manuscript_20261005_v4.tar.gz), [v5](../experiments/runs/paper_author_review_manuscript_20261008_v5.tar.gz), and [v6](../experiments/runs/paper_author_review_manuscript_20261008_v6.tar.gz) archives remain untouched and verify without comparing to the edited workspace. V2 holds the previous 14-page, three-table draft. V3 predates the final recomputation of its historical input-hash ledger. The updated ledger in v4–v7 has SHA-256 `9da89378d1f9b769f5fdc5597ba1dcf666c8453aea53363d9f2d46eea31ccdb0`. V5 updates the AI-use disclosure and adds the independent transformed-receipt recount. V6 adds a read-only original-byte audit. V7 updates the manuscript's data-availability wording and rendered files to match the tracked experiment branch. The historical packaging ledger bytes are absent, and one digest in the current tracked input ledger differs from the archived inventory; see the [audit note](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md).

The filtered package excludes original trajectories, candidate source, model responses, source snapshots, the unredacted original archive, the sanitized review candidate, and unrelated historical JSON. `paper/artifacts/input_hashes.csv` lists historical source hashes, but the hashed raw inputs are not in this package. The tracked v7 audit JSON files also need the separately tracked pilot traces for replay. The included audit scripts require those separate archives; this bundle alone cannot independently regenerate reported numbers from raw logs. It reflects the exploratory paper and an excluded feasibility pilot, not the proposed prospective main study.

The builder screens selected bytes and expanded DOCX members for local home-path/account markers, with zero matches in this package. That limited screen does **not** establish privacy clearance for all metadata, images, or free text. The source tree has other tracked files with local paths. This filtered archive has not been approved as a journal supplement, regardless of the GitHub visibility of the experiment artifacts.

To verify the archive and compare its copies with the current workspace:

```sh
python3 -B -m paper.build_author_review_bundle verify \
  --archive experiments/runs/paper_author_review_manuscript_20261012_v7.tar.gz
```

If the manuscript, form, figures, or tables change, make a new versioned package; do not overwrite this receipt. Authors still need to approve the exact claims and limitations, author metadata and declarations, data-access route, privacy disposition, and venue-specific files using [the decision form](AUTHOR_SUBMISSION_DECISIONS_20261005.md).
