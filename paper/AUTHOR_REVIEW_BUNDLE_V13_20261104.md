# Author-review manuscript bundle — v13, 4 November 2026

The [v13 archive](../experiments/runs/paper_author_review_manuscript_20261104_v13.tar.gz)
is the current filtered **REVIEW_ONLY** copy of the three-author manuscript,
identified and anonymous PDF/DOCX renderings, five article figures and the
standalone stop-label chart, derived tables, and selected audit reports. It has
**60 members**: 58 exact source files, `REVIEW_ONLY_README.md`, and
`SOURCE_HASH_MANIFEST.json`. The [receipt](../experiments/runs/paper_author_review_manuscript_20261104_v13.tar.receipt.json)
records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v13 archive (3,232,819 bytes) | `93cc996fb8ff167b50ba47b7a978b785645d44c92188031888bc79e3fa676a96` |
| Internal source-hash manifest | `ab89436c4b0c1a981546c92cf304da8222e46d64c054f87b4f52e80e3dbf7d84` |

Compared with the [v12 snapshot](AUTHOR_REVIEW_BUNDLE_V12_20261104.md), the
scientific findings are unchanged. This bundle binds the corrected five-figure
render that stays within the 20-page PDF limit with both Arial and the wider
Linux fallback font. The stop-label counts remain in the manuscript text and
the omitted chart remains a separate reproducible asset. Its raw study archives
are tracked separately and are required to replay derived counts. No excluded
pilot is reclassified as eligible main-study data.

The builder verified its file allowlist, SHA-256 manifest, decision bindings,
receipt, and limited local-path screen. The package includes identified author
material and must not be uploaded as an anonymous peer-review supplement. It
does not establish privacy clearance, task security, author approval, or
journal submission readiness. Affiliations, contributions, declarations, and
direct approval from all authors remain pending.

From the repository root:

```sh
python3 -B -m paper.build_author_review_bundle verify --bundle-version v13
python3 -B -m unittest -q paper.test_author_review_bundle paper.test_submission_rendering
```
