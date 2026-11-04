# Author-review manuscript bundle — v16, 4 November 2026

The [v16 archive](../experiments/runs/paper_author_review_manuscript_20261104_v16.tar.gz)
is the current filtered **REVIEW_ONLY** copy of the manuscript and its
identified and anonymous PDF/DOCX renderings. Its **91 members** comprise 89
exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`.
The [receipt](../experiments/runs/paper_author_review_manuscript_20261104_v16.tar.receipt.json)
records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v16 archive (3,286,690 bytes) | `00af397f39982dbf81305fbbc47fe80ed26da6ba01f374e6ec6ba97fc6bd5637` |
| Internal source-hash manifest | `dc667a0f09bc6ebb6d990ae9862a28985af15034d3907a4efab5c61182b1f848` |

Compared with [v15](AUTHOR_REVIEW_BUNDLE_V15_20261104.md), this version binds
rerendered manuscript PDFs after a remote Linux page-limit failure and three
additional derived files: the excluded Qwen3:8b capacity-probe report, JSON
recount, and limited archive-screen receipt. The **raw Qwen archive is not
inside this bundle**. The first Qwen3:8b request timed out after the fixed
300-second request limit, leaving three unstarted slots and no feedback pairs.
The result does not measure a cross-model feedback effect.

The builder verified exact allowlist scope, source hashes, author-decision
bindings, archive receipt, and limited path-marker screen. A deterministic
rebuild produced the same archive hash. The `related_data_public_git_revision`
field remains **null**; this snapshot does not bind a final Git revision for
the newest material. The earlier [v15 bundle](AUTHOR_REVIEW_BUNDLE_V15_20261104.md)
still verifies with `--no-local-compare` as a dated snapshot.

The identified and anonymous PDFs each have 19 pages locally, and a local
simulated fallback stays within 20. The remote Linux recheck after the layout
change is pending. Human author approval, semantic task admission, privacy
clearance, and a journal data route remain pending. The identified author
decision form must not accompany anonymous peer review.

From the repository root:

```sh
python3 -B -m paper.build_author_review_bundle verify --bundle-version v16
python3 -B -m paper.build_author_review_bundle verify --bundle-version v15 --no-local-compare
python3 -B -m unittest -q paper.test_author_review_bundle
paper_python="${PAPER_PYTHON:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
"$paper_python" -B -m unittest -q paper.test_submission_rendering
```
