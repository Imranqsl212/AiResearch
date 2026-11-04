# Author-review manuscript bundle — v12, 4 November 2026

The [v12 archive](../experiments/runs/paper_author_review_manuscript_20261101_v12.tar.gz)
is a filtered **REVIEW_ONLY** snapshot of the three-author draft at its first
4 November rendering, its identified and anonymous PDF/DOCX files, six chart
assets, derived
tables, and selected audit reports. It has **60 members**: 58 source files,
`REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`. The [receipt](../experiments/runs/paper_author_review_manuscript_20261101_v12.tar.receipt.json)
records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v12 archive (3,496,378 bytes) | `4421f04321bb16fee5f6327d47d1cecd9046d8c863a609a10b6b333f8ad47d6a` |
| Internal source-hash manifest | `e4d999e9f8ba12241f46a81d29bfcf1e4fa35912bc0034b969b9ae893f6315d1` |

Compared with the dated v11 snapshot, this bundle adds separate reports and
machine-readable recounts for both stopped temperature-0.3 waves, the exact-
source historical public-feedback match, the older C5 action audit, and a
two-panel descriptive pilot figure. These cohorts have different protocols;
their counts are not pooled. The archive contains derived reports rather than
raw trajectories or candidate code. Their saved raw inputs remain required
for independent replay. The decision form binds the exact current manuscript
and selected derived audits by hash.

The bundle builder verified its file allowlist, selected file hashes, decision
bindings, and limited local-path screen at creation. `verify --bundle-version v12
--no-local-compare` checks its archived receipt after the manuscript changed.
The [v13 package](AUTHOR_REVIEW_BUNDLE_V13_20261104.md) binds the current render. This package does
not establish privacy clearance, external chain of custody, task security,
author approval, or journal submission readiness. It includes the identified
decision form and must not be uploaded as an anonymous peer-review supplement.
Affiliations, individual contributions, declarations, and direct author
approval are pending.

From the repository root:

```sh
python3 -B -m paper.build_author_review_bundle verify --bundle-version v12 --no-local-compare
python3 -B -m unittest -q paper.test_author_review_bundle
```

Earlier bundle versions remain dated snapshots. If current source files change,
use `--no-local-compare` only to verify the old archive receipt, then create a
new review package for the new manuscript rather than treating this one as current.
