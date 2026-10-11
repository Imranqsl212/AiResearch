# Local author-review manuscript bundle — updated 8 October 2026

**Status: REVIEW_ONLY.** This is a filtered local handoff for author inspection, not a public data release, journal supplement, or submitted manuscript.

The current Git-ignored [v6 archive](../experiments/runs/paper_author_review_manuscript_20261008_v6.tar.gz) contains 37 members: 35 exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`. The source files include `paper/final.md`, identified and anonymous PDF/DOCX copies, six figures, `paper/references.bib`, eight historical derived CSV tables, `paper/artifacts/results.json`, the source-fidelity inventory, separate v7 episode and fork audit JSON files, the strategy-coding protocol, the v7 pilot report, the cover-letter template, data-availability options, and the author decision form. The independent transformed-receipt recount and separate local original-byte audit each have their script, focused tests, and methods note in the package. Every source file is copied byte for byte and listed with its SHA-256 and size in the internal manifest. The v7 audits are separate from the historical results and are not pooled with the 40-episode denominator.

| Receipt item | SHA-256 |
| --- | --- |
| v6 review archive | `be08400e1dd8d71083f344e07372e27410e3f23c38c3c387a772a20c36ceca14` |
| v6 internal source-hash manifest | `148d337cdf03a461f404f9d309faa5bd051784f87e539b69d6e778c4527ad47c` |
| Identified PDF | `9ff2101a5b266e573e3c7404eedb46efc3e9a0fdcc44916edc0cbe02be2db621` |
| Identified DOCX | `c644765c009184f1acdfb0e58de2902f1937f78aaca4cd5dbbf6c4460b3c885f` |
| Anonymous PDF | `cf441273640fd14d429cb36647458c0ee60eab45738ea45371079bfe6186e7ca` |
| Anonymous DOCX | `5b575416742753dcc515210b84f67f3c1758ef77c1951c346b35afd554e240fc` |

The adjacent Git-ignored [v6 receipt](../experiments/runs/paper_author_review_manuscript_20261008_v6.tar.receipt.json) records the archive and manifest hashes. The builder used fixed archive metadata and gzip timestamps. Two independent builds produced identical archive bytes in the local test. A SHA-256 receipt detects accidental changes when compared with a trusted copy; it is not a signature or independent timestamp. The older [v1](../experiments/runs/paper_author_review_manuscript_20261005_v1.tar.gz), [v2](../experiments/runs/paper_author_review_manuscript_20261005_v2.tar.gz), [v3](../experiments/runs/paper_author_review_manuscript_20261005_v3.tar.gz), [v4](../experiments/runs/paper_author_review_manuscript_20261005_v4.tar.gz), and [v5](../experiments/runs/paper_author_review_manuscript_20261008_v5.tar.gz) archives remain untouched and verify without comparing to the edited workspace. V2 holds the previous 14-page, three-table draft. V3 contains the revised manuscript but predates the final recomputation of its historical input-hash ledger. The updated ledger in v4–v6 has SHA-256 `9da89378d1f9b769f5fdc5597ba1dcf666c8453aea53363d9f2d46eea31ccdb0`. V5 updates the manuscript AI-use disclosure and cover-letter template, and adds the independent transformed-receipt recount. V6 adds a separate read-only audit that verified the local private original's 313 members against the sanitized manifest and independently recounted 9/20 from original terminal receipts. The historical packaging ledger bytes are absent, and one digest in the current tracked input ledger differs from the private inventory; see the [audit note](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md).

The package excludes original trajectories, candidate source, model responses, private source snapshots, the unredacted private archive, the sanitized review candidate, and unrelated historical JSON. `paper/artifacts/input_hashes.csv` lists historical source hashes, but the hashed raw inputs are not in this package. The tracked v7 audit JSON files also need Git-ignored pilot traces for replay. The included audit scripts require the separate private archives; this bundle alone cannot independently regenerate reported numbers from raw logs. It reflects the exploratory paper and an excluded feasibility pilot, not the proposed prospective main study.

The builder screens selected bytes and expanded DOCX members for local home-path/account markers, with zero matches in this package. That limited screen does **not** establish privacy clearance for all metadata, images, or free text. No human privacy review or public release approval has been recorded. The source tree has other tracked files with local paths, so this filtered archive must not be treated as a repository release.

To verify the archive and compare its copies with the current workspace:

```sh
python3 -B -m paper.build_author_review_bundle verify \
  --archive experiments/runs/paper_author_review_manuscript_20261008_v6.tar.gz
```

If the manuscript, form, figures, or tables change, make a new versioned package; do not overwrite this receipt. Authors still need to approve the exact claims and limitations, author metadata and declarations, data-access route, privacy disposition, and venue-specific files using [the decision form](AUTHOR_SUBMISSION_DECISIONS_20261005.md).
