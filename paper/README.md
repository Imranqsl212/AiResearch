# Manuscript reproduction and handoff

The manuscript in [final.md](final.md) is an exploratory measurement audit with a separate, excluded corrected-oracle pilot. The identified files are [PDF](submission/full_paper.pdf) and [Word](submission/full_paper.docx). The anonymous peer-review files are [PDF](submission/full_paper_anonymous.pdf) and [Word](submission/full_paper_anonymous.docx). It contains six generated PNG figures in `figures/` and four tables. The pre empirical protocol manuscript is preserved in `archive/protocol_before_empirical_revision.md`.

## Required local inputs

The raw historical main and AEAD pilot episodes are under `../experiments/runs/`, with result indexes, manifests, schedules, ledgers, nightly gate report, and sealed archive records under `../experiments/`. The separate v7 corrected-oracle pilot and matched continuation have their own run archives. This research branch tracks these inputs. A complete checkout of this branch can rerun the listed local analyses from source trajectories; a partial export or a checkout lacking the archived inputs cannot. The derived tables in `artifacts/` and v7 audit JSON files do not substitute for raw evidence. Git availability does not approve the records for journal supplementary release.

The 101 receipts in the paper's historical inventory are fixed in
[`historical_receipts_20261003.txt`](historical_receipts_20261003.txt). The
analysis reads that list rather than scanning every later pilot run in
`experiments/runs/`. This keeps the 40-episode exploratory denominator and its
separate historical accounting stable as new C1–C5 experiments are added.

The main experiment identifier is `rag-overnight-v2-main-0-5-0`; the separate pilot identifier is `rag-overnight-v2-pilot-0-5-0`. The study manifest cites Git commit `98a4dcf414672c1725e4acdb9f08045370aa7f64`. The analysis and manuscript were written after collection; their Git state should be recorded at submission. A current source checkout alone may differ from frozen adapter code, so use the study commit to inspect the executed implementation.

## Recompute

From the repository root:

```sh
python3 -B -m analysis.paper_pipeline --output paper/artifacts
python3 -B -m analysis.auxiliary_sidecar_audit
python3 -B -m analysis.source_fidelity_v1 --check
python3 -B -m analysis.audit_v7_decisive_excluded_pilot --check
python3 -B -m analysis.audit_v7_decisive_c5_fork --check
python3 -B -m unittest tests.test_paper_pipeline
```

The historical paper analysis uses the Python standard library. It validates every historical main and AEAD pilot artifact, reads but never executes submitted source, hashes every input before and after analysis, and writes only into `paper/artifacts/`. `results.json` contains group summaries and exploratory family contrasts. `run_metrics.csv` traces every included historical run back to its log and receipt path. `input_hashes.csv` inventories inputs. `historical_inventory.csv` makes exclusions explicit. The separate v7 audit commands reopen their own proof, request, event, and receipt archives and verify the saved excluded-pilot reports. The [source-fidelity audit](../docs/EXPLORATORY_SOURCE_FIDELITY_20261005.md) produces a versioned, code-free inventory of the 77 logged historical sources and 37 adjacent pairs. None of these commands runs the model, Docker, or security experiments.

A separate [sanitized review candidate](SANITIZED_REVIEW_CANDIDATE_20261005.md)
now replays the path-independent paper table sections from transformed archive
bytes using `python3 -B -m paper.replay_sanitized_candidate`. It does not
revalidate original-byte provenance or approve the archive for public release.
An [independent terminal-receipt recount](INDEPENDENT_DISCORDANCE_CHECK_20261008.md)
also verifies the central 9/20 test–gate disagreement from that transformed
archive without importing the historical summary functions. The private
[privacy review register](../docs/SANITIZED_PRIVACY_REVIEW_REGISTER_20261008.md)
keeps all scanner leads pending human disposition.

A separate [read-only original-byte audit](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md)
checks the local private original against the sanitized manifest, both archive
receipts, and the original terminal 9/20 count:

```sh
python3 -B -m paper.audit_original_archive_provenance
python3 -B -m unittest -q paper.test_audit_original_archive_provenance
```

It verified 313 original archive members and their transformed counterparts
locally. The archived input-ledger digest still differs from the current tracked
ledger by one later source hash. This audit does not establish external chain
of custody, rerun the model or evaluator, or clear either archive for release.

The separate auxiliary audit searches local, unsealed Docker sidecar logs by candidate-source hash. Its result is in `artifacts/auxiliary_sidecar_audit.json`. These logs are not uniquely tied to an action and are not used for any paper outcome or stopping metric. A clone without `sandbox/logs/` cannot reproduce this auxiliary check.

The PDF and Word builder requires the versions pinned in
[`requirements-render.txt`](requirements-render.txt). It was last rendered with
Python 3.12.14. From the repository root, run the bundled-runtime wrapper
(or set `PAPER_PYTHON` to a compatible interpreter with those packages):

```sh
sh reproduction/render_paper.sh
```

This command regenerates the six figures and both identified and anonymous
manuscript formats, including four tables, from `final.md`. The abstract has
237 words excluding keywords. The current A4 PDFs have 16 identified pages
and 16 anonymous pages. The anonymous renderer removes the author,
affiliation, and correspondence lines, replaces the acknowledgment body with a
neutral peer-review notice, withholds the source commit, and clears author
metadata from the PDF and Word files. It checks rendered content and document
metadata for known author identifiers. The PDF and Word styles use 12-point
Arial and single line spacing on A4 pages; the renderer reports PDF page counts
and exits with an error if either version exceeds 20 pages. Word page counts
may vary slightly in another application, so inspect the submitted Word copy
in the journal's chosen editor as well.

Run the focused rendering checks with the same Python environment:

```sh
sh reproduction/render_paper.sh
paper_python="${PAPER_PYTHON:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
"$paper_python" -B -m unittest paper.test_submission_rendering
```

The anonymous file is a draft for peer review. Author declarations, data
release, and venue-specific file requirements still need confirmation before
submission.

The current chart builder references macOS Arial in
`/System/Library/Fonts/Supplemental/`; a fully portable build also needs a
compatible TrueType font configured on the destination host. The builder
verifies key numerical anchors before typesetting and extracts text from the
generated PDF to check required sections. Pinning packages alone does not
make the output bitwise reproducible across fonts and operating systems.

## Claims and limitations to retain when sharing

- `16/20` is acceptance by **finite local checks** on nominally repairable final candidates, not a proof of secure code.
- `9/20` policy rejected episodes pass the raw family tests and fail a hidden condition rule. They do not test whether the agent recognizes a genuinely impossible programming requirement.
- `0/81` per-action check records preserve the raw family test result. The terminal disagreement cannot be assigned to an earlier action in the trajectory; extra revisions must not be described as occurring after a known raw pass.
- `0/15` recovered explicit success statements contradict the limited benchmark receipt. Five main final claims were not recovered; the historical raw parser labeled all 40 unknown.
- The five historical main families have one run per arm. Family resampling is descriptive; the planned GEE and independently coded strategy transition outcome are unavailable.
- Of 77 historical logged source strings, 63 parse. Eleven have an unquoted logger redaction marker that causes a syntax error; two have an invalid compound `def` after a semicolon, and one has an unmatched closing brace. The logged archive cannot recover the erased expressions. Only 25/37 adjacent pairs have two parseable logged sources, and their AST/API features are not semantic strategy labels. See the [versioned source-fidelity audit](../docs/EXPLORATORY_SOURCE_FIDELITY_20261005.md).
- The [excluded v7 corrected-oracle pilot](../docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md) completed 30/30 prescheduled episodes at temperature 0.3, with three seeds per cell across two authored families. C3 and C4 used two submissions each in all six matched blocks; one post-outcome-selected secure-onset fork differed under truthful PASS and false FAIL. These observations do not justify a population confidence interval or general feedback-effect claim, and no v7 episode is eligible for the prospective main study.
- A prospective v1 logger now retains full finite-evaluator receipts on checked actions and explicit `NOT_RUN` reasons on non-check actions. This improves future excluded data fidelity; it cannot restore the 81 historical per-action raw results or change the prospective main study's `NOT_READY` status and zero eligible main episodes.

Source links are in the numbered references of the article; an editable BibTeX companion is [references.bib](references.bib). The publication review and unresolved validity findings are documented in [PAPER_SUBMISSION_AUDIT.md](../docs/PAPER_SUBMISSION_AUDIT.md).
The current venue-neutral author handoff and unresolved submission items are in
[`SUBMISSION_HANDOFF_20261005.md`](SUBMISSION_HANDOFF_20261005.md).
