# Author-review manuscript bundle — v15, 4 November 2026

The [v15 archive](../experiments/runs/paper_author_review_manuscript_20261104_v15.tar.gz)
is the current filtered **REVIEW_ONLY** copy of the manuscript and its
identified and anonymous PDF/DOCX renderings. Its **88 members** comprise 86
exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`.
The [receipt](../experiments/runs/paper_author_review_manuscript_20261104_v15.tar.receipt.json)
records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v15 archive (3,283,922 bytes) | `2b57ffb513240720386fa7f0e7ce9380ddae451314b3fdc8ce77e7ebb854998d` |
| Internal source-hash manifest | `3b8957b0585356feef2c6b116bfefc4e8a92fb45a1437c310012f9a7aa08b49b` |

Compared with [v14](AUTHOR_REVIEW_BUNDLE_V14_20261104.md), this version binds
the updated paper and 10 additional derived files: historical protocol-stop
recount, endpoint sensitivity, test-set sufficiency, a checker-stage SVG, and
the excluded Gemma transfer report/JSON plus its limited archive-screen
receipt. The **raw Gemma archive is not inside this bundle**. In the Gemma
pilot all four fixed slots lacked a secure precursor submission; no feedback
pair opened, so no cross-model feedback effect was measured.

The builder verified exact allowlist scope, every source hash, author-decision
bindings, archive receipt, and limited path-marker screen. A deterministic
rebuild produced the same archive hash. The `related_data_public_git_revision`
field remains **null** because this review snapshot does not bind a final Git
revision for the newest material. The older historical-data revision applies
only to its earlier release. The identified decision form must not accompany
anonymous peer review. Human author approval, semantic task admission,
privacy clearance, and a journal data route remain pending.

From the repository root:

```sh
python3 -B -m paper.build_author_review_bundle verify --bundle-version v15
python3 -B -m paper.build_author_review_bundle verify --bundle-version v14 --no-local-compare
python3 -B -m unittest -q paper.test_author_review_bundle
paper_python="${PAPER_PYTHON:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
"$paper_python" -B -m unittest -q paper.test_submission_rendering
```
