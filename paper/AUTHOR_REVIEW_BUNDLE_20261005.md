# Author-review manuscript bundle — v10, 16 October 2026

**Status: REVIEW_ONLY.** This is a filtered handoff for author inspection, not a journal supplement or submitted manuscript. The raw experiment artifacts are tracked separately in the public repository.

The current [v10 archive](../experiments/runs/paper_author_review_manuscript_20261016_v10.tar.gz) contains 39 members: 37 exact source files, `REVIEW_ONLY_README.md`, and `SOURCE_HASH_MANIFEST.json`. The source files include `paper/final.md`, identified and anonymous PDF/DOCX copies, six figures, `paper/references.bib`, eight historical derived CSV tables, `paper/artifacts/results.json`, the source-fidelity inventory, separate v7 episode and fork audit JSON files, the strategy-coding protocol, the v7 pilot report, the cover-letter template, data-availability options, the author decision form, the working author-year conversion, and the dated venue shortlist. The independent transformed-receipt recount and separate local original-byte audit each have their script, focused tests, and methods note in the package. Every source file is copied byte for byte and listed with its SHA-256 and size in the internal manifest. The v7 audits are separate from the historical results and are not pooled with the 40-episode denominator. The archived derived tables preserve earlier exploratory calculations even where the manuscript no longer discusses them. The author-year conversion and venue shortlist are working review materials, not the rendered manuscript or proof of journal compliance.

| Receipt item | SHA-256 |
| --- | --- |
| v10 review archive | `146eb023423c3c3bb5cb38584ade4e50723a82b9281d7edc4a1abaae8e37e436` |
| v10 internal source-hash manifest | `b8a435097da0926a5c8d3c9ff11a174f6c45b4d5f5bda81c44b34287957de098` |
| Identified PDF | `2212e03ec77f66ffebbbfca8481514807258a0105a08f1410387855448a1f502` |
| Identified DOCX | `fe9be94e57bef198f8d60445ad03993f9ae20ebd8f4916afb191417d0c89f703` |
| Anonymous PDF | `942eedc00d6586e58ca472ed1d1cc9c240875619c76077c0727b46a0a9d8bc95` |
| Anonymous DOCX | `238dca97d1da5ee262992010d4944fd023e9cd058998861aa410fd589ea2be73` |

The adjacent tracked [v10 receipt](../experiments/runs/paper_author_review_manuscript_20261016_v10.tar.receipt.json) records the archive and manifest hashes. The builder uses fixed archive metadata and gzip timestamps. Two independent builds produce identical archive bytes in the local test. A SHA-256 receipt detects accidental changes when compared with a trusted copy; it is not a signature or independent timestamp. The older v1–v9 archives remain untouched and verify without comparing to the edited workspace. V10 includes the current input ledger with SHA-256 `cbb4e7821aba6b588bcf5e96ea13737ad3f5c081b147966d934391db2a9c9c98`; v4–v9 contain the prior ledger with SHA-256 `9da89378d1f9b769f5fdc5597ba1dcf666c8453aea53363d9f2d46eea31ccdb0`. The historical packaging ledger bytes are absent, and three digests in the current tracked input ledger differ from the archived inventory; see the [audit note](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md).

The filtered package excludes original trajectories, candidate source, model responses, source snapshots, the unredacted original archive, the sanitized review candidate, and unrelated historical JSON. `paper/artifacts/input_hashes.csv` lists historical source hashes, but the hashed raw inputs are not in this package. The tracked v7 audit JSON files also need the separately tracked pilot traces for replay. The included audit scripts require those separate archives; this bundle alone cannot independently regenerate reported numbers from raw logs. It reflects the exploratory paper and an excluded feasibility pilot, not the proposed prospective main study.

The builder screens selected bytes and expanded DOCX members for local home-path/account markers, with zero matches in this package. That limited screen does **not** establish privacy clearance for all metadata, images, or free text. The source tree has other tracked files with local paths. This filtered archive has not been approved as a journal supplement. The v10 manifest records the public GitHub data revision but does not attest to the review archive's Git visibility.

To verify the archive and compare its copies with the current workspace:

```sh
python3 -B -m paper.build_author_review_bundle verify \
  --archive experiments/runs/paper_author_review_manuscript_20261016_v10.tar.gz
```

If the manuscript, form, figures, or tables change, make a new versioned package; do not overwrite this receipt. Authors still need to approve the exact claims and limitations, author metadata and declarations, data-access route, privacy disposition, and venue-specific files using [the decision form](AUTHOR_SUBMISSION_DECISIONS_20261005.md).
