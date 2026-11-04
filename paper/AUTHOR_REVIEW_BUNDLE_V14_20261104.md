# Author-review manuscript bundle — v14, 4 November 2026

The [v14 archive](../experiments/runs/paper_author_review_manuscript_20261104_v14.tar.gz)
is the current filtered **REVIEW_ONLY** copy of the manuscript and its
identified and anonymous PDF/DOCX renderings. Its **78 members** comprise 76
exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`.
The [receipt](../experiments/runs/paper_author_review_manuscript_20261104_v14.tar.receipt.json)
records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v14 archive (3,262,586 bytes) | `8f260229e2b0732be1147ea67b8edeb112ac04a47cbca952f7e398b3684e580c` |
| Internal source-hash manifest | `cc5287127b1860623ed043b35311e1026f5411677a3ef8f38d987f843fb59f9f` |

Compared with [v13](AUTHOR_REVIEW_BUNDLE_V13_20261104.md), this version
binds the revised paper and 18 additional **derived** reports/JSON recounts:
historical feedback specificity, first-candidate parity, leave-one-world-out
checker sensitivity, directional errors, logged-source surrogate ASTs, and
the separate three-family and six-slot live waves. The raw trajectories,
model responses, source snapshots, and separately tracked run archives are
outside this bundle. The new analyses remain exploratory; none creates an
eligible prospective main episode.

The builder verified the exact allowlist, every file hash, the author-decision
bindings, receipt, and limited path-marker screen. The `related_data_public_git_revision`
field is deliberately **null** because this review snapshot does not bind a
final Git revision for the newest wave. The older historical-data revision
applies only to its earlier release. This package includes identified author
material and must not be sent as an anonymous peer-review supplement. Human
author approval, semantic task admission, privacy clearance, and a journal
data route are still pending.

From the repository root:

```sh
python3 -B -m paper.build_author_review_bundle verify --bundle-version v14
python3 -B -m paper.build_author_review_bundle verify --bundle-version v13 --no-local-compare
python3 -B -m unittest -q paper.test_author_review_bundle paper.test_submission_rendering
```
