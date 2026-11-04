# Author-review manuscript bundle — v18, 4 November 2026

The [v18 archive](../experiments/runs/paper_author_review_manuscript_20261104_v18.tar.gz)
is the current filtered **REVIEW_ONLY** copy of the manuscript and its
identified and anonymous PDF/DOCX renderings. Its **100 members** comprise 98
exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`.
The [receipt](../experiments/runs/paper_author_review_manuscript_20261104_v18.tar.receipt.json)
records the archive and internal manifest digests.

| Artifact | SHA-256 |
| --- | --- |
| v18 archive (3,303,992 bytes) | `2e279c1224169fb82c83d82bccb1b8b0b6aac6d595198d6cfd42d3c7ae77d7fc` |
| Internal source-hash manifest | `a232d31443ec3ac9c89ad4d63fd4284d698bf32280e15ba55dcd2bf4155da8e8` |

Compared with [v17](AUTHOR_REVIEW_BUNDLE_V17_20261104.md), this version
binds the revised paper and nine additional derived files: source-bound
historical terminate-latency report/JSON/script/test/SVG, and a separate
excluded v7 provider-latency report/JSON/script/test. The former found that
14 of 40 historical episodes had an acknowledged `terminate` request; 13
later self-labeled episodes had a median 128.446-second interval from first
acknowledgement to final runner stop. This is observed time, not a measured
time saving. The latter audited 208 completed qwen3:4b responses in five
selected cohorts and found a latency burst in one stopped wave; it cannot
identify the cause or a feedback effect. Raw run archives remain outside
this filtered bundle.

The builder verified the exact allowlist, source hashes, author-decision
bindings, archive receipt, and limited path-marker screen. A deterministic
rebuild produced the same archive hash. The `related_data_public_git_revision`
field remains **null**; the package does not bind a final Git revision for
the newest material. [V17](AUTHOR_REVIEW_BUNDLE_V17_20261104.md) remains a
dated snapshot and verifies with `--no-local-compare`.

The previous V17 remote Linux manuscript-format check passed at source
revision `42aaa05e`. The V18 PDFs have 18 pages locally; a fresh-process
Bitstream Vera check stays within 20 pages. The remote Linux recheck of V18
is pending. Human author approval, semantic task admission, privacy
clearance, and a journal data route remain pending. The identified decision
form must not accompany anonymous peer review.

From the repository root:

```sh
python3 -B -m paper.build_author_review_bundle verify --bundle-version v18
python3 -B -m paper.build_author_review_bundle verify --bundle-version v17 --no-local-compare
python3 -B -m unittest -q paper.test_author_review_bundle
paper_python="${PAPER_PYTHON:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
"$paper_python" -B -m unittest -q paper.test_submission_rendering
```
