# Author-review manuscript bundle — v11, 1 November 2026

The new [v11 archive](../experiments/runs/paper_author_review_manuscript_20261101_v11.tar.gz) is a **REVIEW_ONLY** copy of the updated manuscript and derived results. It has 51 members: 49 exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`. The [receipt](../experiments/runs/paper_author_review_manuscript_20261101_v11.tar.receipt.json) records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v11 archive (3,337,641 bytes) | `8735ed39ebea7fa6a0ace7aff698b6698edf45a731bbb99338162ae51e374e58` |
| Internal source-hash manifest | `1185b7f0df375fd8f5174fb7bcbf1b973aa01c03c76f4fef332c1acd5489b060` |

V11 retains the v10 filtered source set and adds four rendered author-year PDF/DOCX files plus derived Markdown and JSON for the older 14-pair regression recount, its 45-submission candidate audit, and the two sequential one-shot v7 waves. The new reports are explicitly excluded pilots with different protocols. The archive contains no raw trajectories, original model responses, candidate code, source snapshots, or original archives; those separately tracked inputs are required to independently replay the counts. The derived reports and PDFs alone cannot prove the underlying observations.

The builder's source allowlist, per-file SHA-256 manifest, pending-decision hash checks, and limited local-path screen passed. A second build had identical archive bytes. An additional scan found no common credential patterns in the selected archive members. These screens are limited: author review of free text, metadata, images, scientific claims, and journal data requirements remains pending. The old `37074c198237ade67eb76921333b2835d329c863` public data revision is explicitly historical; v11 does not bind a public revision for the new pilot archives, attest to Git visibility, or authorize journal release. The decision form and identified files must not be included in an anonymous peer-review submission.

V1–v10 remain immutable historical packages. In particular, the [v10 note](AUTHOR_REVIEW_BUNDLE_20261005.md) and its archive still verify against their own receipt without comparison to the updated workspace.

From the repository root, verify v11 against the current selected sources:

```sh
python3 -B -m paper.build_author_review_bundle verify \
  --archive experiments/runs/paper_author_review_manuscript_20261101_v11.tar.gz
python3 -B -m unittest -q paper.test_author_review_bundle
```

If the selected sources later change, use `--no-local-compare` to verify only the archived bytes and receipt. A digest is not an independent timestamp, digital signature, or final source revision. Make v12 rather than overwriting v11 after any later manuscript or decision-form change.
