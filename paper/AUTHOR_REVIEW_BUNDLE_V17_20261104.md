# Author-review manuscript bundle — v17, 4 November 2026

The [v17 archive](../experiments/runs/paper_author_review_manuscript_20261104_v17.tar.gz)
is the current filtered **REVIEW_ONLY** copy of the manuscript and its
identified and anonymous PDF/DOCX renderings. Its **91 members** comprise 89
exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`.
The [receipt](../experiments/runs/paper_author_review_manuscript_20261104_v17.tar.receipt.json)
records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v17 archive (3,282,679 bytes) | `5f82c54fb2fae9e79df955e4fdd783c042f6847613de1c85d88b9a08b09015cc` |
| Internal source-hash manifest | `f89ec2de24f91e39c2d92e875b5e569a671a8d8ed1934ec488d53d78df326adc` |

Compared with [v16](AUTHOR_REVIEW_BUNDLE_V16_20261104.md), the selected
source-file list is unchanged. This version binds revised `final.md` and
identified/anonymous PDF/DOCX files after a real fallback-font issue was
found: an earlier local test reused an Arial font registration instead of
embedding Bitstream Vera. The fresh-process Vera render now has **19 pages**
for each manuscript, and the local Arial render has **18 pages**. The remote
Linux recheck after this correction is pending; this bundle does not claim
that CI has passed.

The builder verified exact allowlist scope, source hashes, author-decision
bindings, archive receipt, and limited path-marker screen. A deterministic
rebuild produced the same archive hash. The `related_data_public_git_revision`
field remains **null**; this snapshot does not bind a final Git revision for
the newest material. The [v16 bundle](AUTHOR_REVIEW_BUNDLE_V16_20261104.md)
still verifies with `--no-local-compare` as a dated snapshot. Raw run archives
are outside this filtered package.

The identified decision form must not accompany anonymous peer review.
Human author approval, semantic task admission, privacy clearance, and a
journal data route remain pending.

From the repository root:

```sh
python3 -B -m paper.build_author_review_bundle verify --bundle-version v17
python3 -B -m paper.build_author_review_bundle verify --bundle-version v16 --no-local-compare
python3 -B -m unittest -q paper.test_author_review_bundle
paper_python="${PAPER_PYTHON:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
"$paper_python" -B -m unittest -q paper.test_submission_rendering
```
