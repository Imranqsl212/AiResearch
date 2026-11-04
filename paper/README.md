# Manuscript reproduction and handoff

The manuscript in [final.md](final.md) is an exploratory measurement audit with a separate, excluded corrected-oracle pilot, a post hoc older C5 candidate audit, sequential one-shot engineering waves, and later directional-error analyses. The identified files are [PDF](submission/full_paper.pdf) and [Word](submission/full_paper.docx). The anonymous peer-review files are [PDF](submission/full_paper_anonymous.pdf) and [Word](submission/full_paper_anonymous.docx). It contains five article figures, a separate stop-label chart in `figures/`, and six tables. The pre empirical protocol manuscript is preserved in `archive/protocol_before_empirical_revision.md`.

The current filtered [v15 author-review bundle](AUTHOR_REVIEW_BUNDLE_V15_20261104.md) binds the revised manuscript, renderings, and selected new derived reports. [V14](AUTHOR_REVIEW_BUNDLE_V14_20261104.md) and earlier bundles are dated snapshots and remain available for audit.

An [author–year venue-format draft](VENUE_FORMAT_DRAFT_20261016.md) has separate identified and anonymous PDF/DOCX files. It preserves the scientific text, figures, and tables while changing citation style; the numbered `final.md` remains the canonical author-review source until a journal and final declarations are approved.

The [17 October collected-data milestone](milestone/RESULTS_20261017.md) organizes the historical and pilot cohorts, adds a graph of the hidden test–gate veto, and compares the observations with the original H1–H6 hypotheses without treating the exploratory records as confirmatory tests.

## Required local inputs

The raw historical main and AEAD pilot episodes are under `../experiments/runs/`, with result indexes, manifests, schedules, ledgers, nightly gate report, and sealed archive records under `../experiments/`. The separate v7 corrected-oracle pilot and matched continuation have their own run archives. The public repository's historical data revision `37074c198237ade67eb76921333b2835d329c863` tracks those earlier inputs; it does not identify the later 14-pair recount or one-shot wave archives. A complete checkout containing all corresponding archives can rerun the listed analyses from source trajectories; a partial export or a checkout lacking the archived inputs cannot. The derived tables in `artifacts/` and v7 audit JSON files do not substitute for raw evidence. GitHub availability does not approve the records for journal supplementary release.

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
python3 -B -m analysis.source_fidelity_v1 --check
python3 -B -m analysis.audit_v7_decisive_excluded_pilot --check
python3 -B -m analysis.audit_v7_decisive_c5_fork --check
python3 -B -m analysis.c5_paired_regression_recount_20261101 --check
python3 -B -m analysis.c5_candidate_discordance_20261101 --check
python3 -B -m analysis.fresh_matched_verdict_pilot_20261101 --check
python3 -B -m analysis.v7_second_wave_20261101 --check
python3 -B -m analysis.historical_matched_source_feedback_20261104 --check
python3 -B -m analysis.historical_feedback_specificity_20261104 --check
python3 -B -m analysis.logged_source_surrogate_ast_20261104 --check
python3 -B -m analysis.c5_feedback_action_20261104 --check
python3 -B -m analysis.c5_first_submission_parity_20261104 --check
python3 -B -m analysis.v7_temp_variance_20261101 --check
python3 -B -m analysis.v7_temp_variance_secondwave_20261101 --check
python3 -B -m analysis.v7_temp03_error_direction_20261104 --check
python3 -B -m analysis.v7_crossfamily_20261104 --check
python3 -B -m analysis.v7_crossfamily_error_direction_20261104 --check
python3 -B -m analysis.v7_feedback_replication_20261104 --check
python3 -B -m analysis.v7_csrf_transition_direction_20261104 --check
python3 -B -m unittest tests.test_paper_pipeline
```

The historical paper analysis uses the Python standard library. It validates every historical main and AEAD pilot artifact, reads but never executes submitted source, hashes every input before and after analysis, and writes only into `paper/artifacts/`. `results.json` contains group summaries and exploratory family contrasts. `run_metrics.csv` traces every included historical run back to its log and receipt path. `input_hashes.csv` inventories inputs. `historical_inventory.csv` makes exclusions explicit. The separate v7 audit commands reopen their own proof, request, event, and receipt archives. The older C5 recounts verify their separate 14-pair archive and recompute all 45 post-onset candidate results; the two later one-shot wave recounts verify each wave separately. None is pooled with the historical or corrected-pilot denominators. The [source-fidelity audit](../docs/EXPLORATORY_SOURCE_FIDELITY_20261005.md) produces a versioned, code-free inventory of the 77 logged historical sources and 37 adjacent pairs. None of these commands runs the model, Docker, or security experiments.

A separate [sanitized review candidate](SANITIZED_REVIEW_CANDIDATE_20261005.md)
now replays the path-independent paper table sections from transformed archive
bytes using `python3 -B -m paper.replay_sanitized_candidate`. It does not
revalidate original-byte provenance or approve the archive as a journal supplement.
An [independent terminal-receipt recount](INDEPENDENT_DISCORDANCE_CHECK_20261008.md)
also verifies the central 9/20 test–gate disagreement from that transformed
archive without importing the historical summary functions. The
[privacy review register](../docs/SANITIZED_PRIVACY_REVIEW_REGISTER_20261008.md)
keeps all scanner leads pending human disposition. Its source inspection packet
and blank register are tracked publicly despite their `PRIVATE` filenames.

A separate [read-only original-byte audit](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md)
checks the original archive, now tracked publicly despite its `private` filename,
against the sanitized manifest, both archive
receipts, and the original terminal 9/20 count:

```sh
python3 -B -m paper.audit_original_archive_provenance
python3 -B -m unittest -q paper.test_audit_original_archive_provenance
```

It verified 313 original archive members and their transformed counterparts
locally. The archived input-ledger digest still differs from the current tracked
ledger: 308 of 311 entries match and three later source/document hashes differ.
This audit does not establish external chain
of custody, rerun the model or evaluator, or clear either archive for a journal deposit.

The separate auxiliary audit searches local, unsealed Docker sidecar logs by candidate-source hash. Its result is in `artifacts/auxiliary_sidecar_audit.json`. These logs are not uniquely tied to an action and are not used for any paper outcome or stopping metric. It is an **original-workspace-only** check: the old auxiliary rows contain absolute trajectory paths, and the ignored `sandbox/logs/` are not in a fresh clone. Run `python3 -B -m analysis.auxiliary_sidecar_audit` only in the original capture workspace with those paths and logs present; it is not part of the portable recompute block above.

The PDF and Word builder requires the versions pinned in
[`requirements-render.txt`](requirements-render.txt). It was last rendered with
Python 3.12.14. From the repository root, run the bundled-runtime wrapper
(or set `PAPER_PYTHON` to a compatible interpreter with those packages):

```sh
sh reproduction/render_paper.sh
```

This command regenerates six chart assets (five embedded in the article) and both identified and anonymous
manuscript formats, including six tables, from `final.md`. The abstract has
220 space-delimited words excluding keywords. The current A4 PDFs have 19
identified and 19 anonymous pages locally; the Linux fallback render reaches
20. The anonymous renderer removes the author,
affiliation, and correspondence lines, replaces the acknowledgment body with a
neutral peer-review notice, withholds the source and public data commits, and clears author
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

The renderer uses macOS Arial where available and falls back to the Bitstream
Vera font pair bundled with the pinned ReportLab package on other systems.
The fallback uses 0.42-inch A4 margins versus 0.52-inch margins for the
canonical Arial render; both retain 12-point text and single spacing. Font
metrics can still change page breaks, so check the page limit in the destination
environment. The builder
verifies key numerical anchors before typesetting and extracts text from the
generated PDF to check required sections. Pinning packages alone does not
make the output bitwise reproducible across fonts and operating systems.

## Claims and limitations to retain when sharing

- `16/20` is acceptance by **finite local checks** on nominally repairable final candidates, not a proof of secure code.
- `9/20` policy rejected episodes pass the raw family tests and fail a hidden condition rule. They do not test whether the agent recognizes a genuinely impossible programming requirement.
- `0/81` per-action check records preserve the raw family test result. The terminal disagreement cannot be assigned to an earlier action in the trajectory; extra revisions must not be described as occurring after a known raw pass.
- `0/15` recovered explicit success statements contradict the limited benchmark receipt. Five main final claims were not recovered; the historical raw parser labeled all 40 unknown.
- The five historical main families have one run per arm. Factor comparisons are descriptive; independently coded strategy transitions and confirmatory hypothesis tests are unavailable.
- The standalone [runner stop-label chart](figures/figure4_stopping.png) remains reproducible but is omitted from the current article to keep the PDF within 20 pages across supported fonts. The text retains the recorded counts: 38 self termination labels, one budget stop, and one timeout. These labels do not verify agent intent. Four of 40 main runs crossed the effective 900-second boundary before the stop event. Three retained a self-termination label after the boundary; in slot `000022`, an explicit `terminate` call at 909.5 seconds preceded the recorded timeout. The accepted candidate in that run is counted separately from its stop label.
- Of 77 historical logged source strings, 63 parse. Eleven have an unquoted logger redaction marker that causes a syntax error; all 11 become parseable if the marker is replaced with a quoted dummy value, but this produces a surrogate AST and does not recover the erased original expression. Two other strings have an invalid compound `def` after a semicolon, and one has an unmatched closing brace. Only 25/37 adjacent pairs have two parseable logged sources, and their AST/API features are not semantic strategy labels. See the [versioned source-fidelity audit](../docs/EXPLORATORY_SOURCE_FIDELITY_20261005.md).
- The [excluded v7 corrected-oracle pilot](../docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md) completed 30/30 prescheduled episodes at temperature 0.3, with three seeds per cell across two authored families. C3 and C4 used two submissions each in all six matched blocks; one post-outcome-selected secure-onset fork differed under truthful PASS and false FAIL. These observations do not justify a population confidence interval or general feedback-effect claim, and no v7 episode is eligible for the prospective main study.
- The separate [post hoc C5 candidate audit](../analysis/C5_CANDIDATE_DISCORDANCE_20261101.md) recounts 45 submissions in 14 selected continuation pairs from an older persistent-veto protocol. A raw check passed while the bounded oracle failed in 21/45 submissions, but those involved only nine distinct candidate hashes; terminal regressions were 5/14 after truthful PASS and 7/14 after false FAIL. This is not a population rate or a causal feedback estimate, and it is not pooled with the 30-episode pilot or the newer one-shot pilot.
- The [first](../analysis/FRESH_MATCHED_VERDICT_PILOT_20261101.md) and [second](../analysis/V7_SECOND_WAVE_20261101.md) one-shot waves were planned sequentially. They retained all eight precursor slots and opened three and two eligible pairs. Terminal bounded-property regression was 0/3 versus 1/3 after truthful PASS versus false FAIL in wave 1, then 1/2 versus 1/2 in wave 2. The first-wave CSRF trajectory repeats an earlier selected case exactly; in the second wave, the signature pair regresses in both arms. These excluded, unadmitted tasks provide no pooled effect estimate.
- A prospective v1 logger now retains full finite-evaluator receipts on checked actions and explicit `NOT_RUN` reasons on non-check actions. This improves future excluded data fidelity; it cannot restore the 81 historical per-action raw results or change the prospective main study's `NOT_READY` status and zero eligible main episodes.

Source links are in the numbered references of the article; an editable BibTeX companion is [references.bib](references.bib). The publication review and unresolved validity findings are documented in [PAPER_SUBMISSION_AUDIT.md](../docs/PAPER_SUBMISSION_AUDIT.md).
The current venue-neutral author handoff and unresolved submission items are in
[`SUBMISSION_HANDOFF_20261005.md`](SUBMISSION_HANDOFF_20261005.md).
