# Author-review manuscript bundle — v19, 4 November 2026

The [v19 archive](../experiments/runs/paper_author_review_manuscript_20261104_v19.tar.gz)
is the current filtered **REVIEW_ONLY** copy of the manuscript and its
identified and anonymous PDF/DOCX renderings. Its **109 members** comprise
107 exact source files, `REVIEW_ONLY_README.md`, and
`SOURCE_HASH_MANIFEST.json`. The [receipt](../experiments/runs/paper_author_review_manuscript_20261104_v19.tar.receipt.json)
records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v19 archive (3,318,249 bytes) | `e3a2d420886b596ada485e45cb5b2d7d9da15a535e37b7d0aff6e72f233f2055` |
| Internal source-hash manifest | `eb5db15615bdb588eb65f0971bab2adf2db8a32c6330f471da42918ec4d390b6` |

Compared with [v18](AUTHOR_REVIEW_BUNDLE_V18_20261104.md), this version
binds revised manuscript/rendering bytes, the corrected historical
terminate-latency audit and SVG, eight new source-bound control files, and
the current rendering test that checks the abstract's 200–250-word range.
The [latency challenge](../analysis/STOP_LATENCY_CHALLENGE_20261104.md)
shows that all 14 historical episodes with an acknowledged `terminate` call
followed public PASS in nominally repairable cells. They contain 15 calls
because one episode called twice. The
[model-free control](../analysis/STOP_CONTRACT_CONTROL_20261104.md) confirms
that the frozen runner needed a later adapter stop decision after acknowledging
`terminate`. The 128.446-second historical median is an observed interval on
the success path, **not** a measure of failure to recognize an unavailable
task or a counterfactual time saving. Raw run archives are outside this
filtered bundle.

The builder verified exact allowlist scope, source hashes, author-decision
bindings, archive receipt, and limited path-marker screen. A deterministic
rebuild produced the same archive hash. The `related_data_public_git_revision`
field remains **null**; the package does not bind a final Git revision for
the newest material. [V18](AUTHOR_REVIEW_BUNDLE_V18_20261104.md) remains a
dated snapshot and verifies with `--no-local-compare`.

The abstract has 204 space-delimited words. The identified and anonymous PDFs
have 18 pages locally with Arial and 19 with a fresh-process Bitstream Vera
render. The current remote Linux recheck is pending. Human author approval,
semantic task admission, privacy clearance, and a journal data route remain
pending. The identified decision form must not accompany anonymous peer review.

From the repository root:

```sh
python3 -B -m paper.build_author_review_bundle verify --bundle-version v19
python3 -B -m paper.build_author_review_bundle verify --bundle-version v18 --no-local-compare
python3 -B -m unittest -q paper.test_author_review_bundle
paper_python="${PAPER_PYTHON:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
"$paper_python" -B -m unittest -q paper.test_submission_rendering
```
