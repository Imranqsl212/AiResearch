# Submission handoff — updated 8 October 2026

## Scope of this manuscript

[`final.md`](final.md) is a venue-neutral **exploratory measurement audit** of the
completed October 2026 local cohort: 40 main episodes from five selected families,
with eight disjoint AEAD pilot episodes described separately. Its central observation
is 9/20 final candidates in nominally unavailable conditions that passed the raw
family tests but failed a hidden acceptance gate. It does not estimate a causal
effect of feedback, retrieval, or model choice, nor does it validate unrestricted
software security. The manuscript now also reports a **separate, excluded**
30-episode v7 corrected-oracle finite pilot with three seeds per cell in two
authored families, plus one selected matched secure-onset continuation. These
pilots are not pooled with the historical 40 episodes. The prospective main
study remains `NOT_READY` with zero eligible new main episodes.

## Files ready for author review

| File | Purpose |
| --- | --- |
| [`final.md`](final.md) | Editable source manuscript, with 25 numbered references and the required IMRAD sections. |
| [`submission/full_paper.pdf`](submission/full_paper.pdf) | Identified 16-page A4 review copy with six figures and four tables. |
| [`submission/full_paper.docx`](submission/full_paper.docx) | Identified editable Word copy. |
| [`submission/full_paper_anonymous.pdf`](submission/full_paper_anonymous.pdf) | Anonymous 15-page A4 review copy. |
| [`submission/full_paper_anonymous.docx`](submission/full_paper_anonymous.docx) | Anonymous editable Word copy. |
| [`references.bib`](references.bib) | Bibliography metadata for journal conversion. |
| [`requirements-render.txt`](requirements-render.txt) | Pinned Python package versions used to render the review PDF and DOCX; a compatible font is still required. |
| [`artifacts/results.json`](artifacts/results.json) | Recomputed exploratory counts and explicit null confirmatory outcomes. |
| [`ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md`](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md) | Local original-to-sanitized byte-link audit and original terminal 9/20 recount; no release clearance. |
| [`../analysis/source_fidelity_v1.json`](../analysis/source_fidelity_v1.json) | Versioned, source-text-free inventory of all 77 logged historical source strings and 37 adjacent pairs. |
| [`../docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md`](../docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md) | Separate v7 pilot protocol, results, matched fork and scope limits. |
| [`historical_receipts_20261003.txt`](historical_receipts_20261003.txt) | Saved allowlist of the 101 legacy receipts inventoried by the paper analysis; include it in the submission source revision. |
| [`submission/cover_letter_template.md`](submission/cover_letter_template.md) | Venue-neutral cover letter draft with author and journal declarations left for confirmation. |
| [`DATA_AVAILABILITY_OPTIONS_20261005.md`](DATA_AVAILABILITY_OPTIONS_20261005.md) | Truthful current status and conditional public/controlled-access wording for author choice. |
| [`VENUE_SHORTLIST_20261005.md`](VENUE_SHORTLIST_20261005.md) | Official-guideline comparison of three possible journals; venue choice remains with the submitting author. |
| [`AUTHOR_SUBMISSION_DECISIONS_20261005.md`](AUTHOR_SUBMISSION_DECISIONS_20261005.md) | Hash-bound draft inventory and the human decisions still pending; it contains no inferred approvals. |

The filtered [v6 local author-review bundle](AUTHOR_REVIEW_BUNDLE_20261005.md)
contains this manuscript, both rendered file pairs, derived v7 pilot audits,
the source-fidelity inventory, an independent transformed-receipt recount,
and the separate original-byte audit code, tests, and methods note.
Its 35 selected sources and two bundle
metadata members verified against the current workspace. It remains
`REVIEW_ONLY`; it excludes the raw trajectories and does not approve data
release or journal submission. Earlier bundles remain separately verifiable;
v2 contains the 14-page, three-table draft, and v3 predates the final
recalculation of the historical input-hash ledger. V4 preserves the prior
manuscript wording, while v5 preserves the earlier transformed-only audit.
All bundles include author
identity and must not be uploaded as anonymous supplements.

A **private author-review copy** of the 311 historical paper input members is saved at
`experiments/runs/paper_private_repro_inputs_20261005.tar.gz` (SHA-256
`39ded8a4301ba0ebb193b48d71b032b0127a521c381fa378c67d08132319fc26`).
The bundle was reopened and every archived member byte-checked after writing.
The archived private inventory's input-ledger digest is not the digest of the
current tracked CSV: 310 of 311 member hashes still match, and the one changed
workspace digest is `experiments/executable_episode.py`. The original CSV bytes
were not stored as an archive member; do not claim the current CSV is the exact
historical packaging ledger.
Its notice marks it `PRIVATE_REVIEW_ONLY_UNREDACTED`; 184 files contain the
local username/path marker. This package is for release review, **not** a
public supplement or a journal upload. The reproducible builder is
[`build_private_repro_bundle.py`](build_private_repro_bundle.py), and the
Git-ignored companion receipt is beside the archive.
This earlier private copy covers the historical paper inputs; the new v7 pilot
has separate Git-ignored source-bound archives and audit receipts.

A separate [sanitized review candidate](SANITIZED_REVIEW_CANDIDATE_20261005.md)
is also saved locally, with an original-to-transformed hash map and a targeted
path/username scan. It changes 200 data members and cannot replay the paper's
original hash chain. A new [table-only verifier](replay_sanitized_candidate.py)
recomputed 13 result sections and all 86 submitted source hashes from the
transformed bytes, matching the tracked paper artifacts without reading the
private original. The sanitized candidate is **not an approved release**;
human privacy/content review and an actual data-availability plan remain
necessary.
The [private inspection packet](../experiments/runs/paper_sanitized_privacy_packet_20261005_v2/PRIVATE_INSPECTION_REPORT.json)
pinpoints the eight residual path candidates and 457 additional lexical leads
for that review. It is Git-ignored, mode `0600`, and explicitly records that
privacy review and public-release approval are pending. Its contents must
not be attached to a journal submission without review.
The [tracked-path privacy audit](../docs/TRACKED_PATH_PRIVACY_AUDIT_20261005.md)
also found local home-path strings in historical tracked JSON and a safety
probe. A public repository or supplementary release needs a separate review
of those files and Git history; the current manuscript PDF/DOCX are review
copies, not an approved public data package.

The new related-work paragraph explicitly discusses SWE-Bench+, PatchBench, and a
recent agentic-security harness audit. It narrows the contribution to this
repair evaluator's raw-test/acceptance disagreement and the resulting limitation
on stopping claims; it does not assert priority over those studies.
An independent manuscript check found the historical numerical anchors
consistent with `artifacts/results.json`. The v7 pilot and matched fork have
separate [episode](../analysis/v7_decisive_excluded_audit_20261005.json) and
[fork](../analysis/v7_decisive_c5_fork_audit_20261005.json) audit reports, both
rechecked against their local raw artifacts. The abstract has 237
whitespace-delimited words excluding the keywords line. The manuscript now
contains six figures and four tables and follows Title,
Authors/Affiliation, Abstract, Introduction, Methods, Results, Discussion,
Acknowledgments, and References. The identified and anonymous PDFs were rebuilt
at 12 pt and single spacing. The identified PDF is 16 A4 pages; the anonymous
PDF is 15. The Word styles are 12 pt and single spaced. The anonymous renderer
checks author identifiers and study-commit markers in text and metadata; repeat
the scan after each content or rendering change. The Word page count was not
independently verified in a Word-compatible editor.
The [source-fidelity audit](../docs/EXPLORATORY_SOURCE_FIDELITY_20261005.md)
identifies the exact historical syntax failures: 11 unquoted logger redaction
markers, two invalid compound `def` statements after semicolons, and one
unmatched closing brace. It cannot reconstruct erased original expressions or
create ASTs for all 77 submissions. The historical 25/37 parseable-pair
denominator and 17 called-API inventory changes remain descriptive.
The prospective v1 logger now retains full finite-evaluator receipts on checked
actions and explicit `NOT_RUN` reasons elsewhere, but cannot backfill the 81
historical per-action records. Three v7 seeds per cell across two authored
families and one selected fork do not support general confidence intervals or
a population feedback effect.
An [independent transformed-receipt check](INDEPENDENT_DISCORDANCE_CHECK_20261008.md)
recounted the central historical 9/20 disagreement directly from the sanitized
terminal receipts without using the original paper summary functions. It
cannot by itself prove original-byte provenance or approve data release. A
[separate original-byte audit](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md)
opened the local private archive, verified all 313 original members against
the sanitization manifest, and independently recounted **9/20** from original
terminal receipts. It does not establish an external chain of custody, run the
evaluator, or clear the archive for public sharing. The new
[private review register](../docs/SANITIZED_PRIVACY_REVIEW_REGISTER_20261008.md)
tracks all residual scanner leads with human decisions still blank.
The current manuscript and analysis remain a working-tree review draft; no
final source revision has yet been pinned.

## What a submitting author must supply or decide

1. Confirm sole authorship and contribution wording. Imran Zakirov provided
   Bishkek, Kyrgyzstan, no institutional affiliation, and the contact email
   shown on the identified title page. The author will clarify funding,
   conflicts, acknowledgments, and other declarations separately; the draft
   discloses Codex assistance for author review. Do not infer missing entries.
2. Select a specific journal or conference article type using the
   [venue shortlist](VENUE_SHORTLIST_20261005.md) as a starting point. Apply its length,
   reference, figure, data-availability, ethics, anonymization, and preprint rules.
   The PDF/DOCX are review copies, not a journal template or an actual submission.
3. Decide how to provide the Git-ignored raw trajectories and archive. A reviewed
   release or controlled-access plan must preserve log-to-receipt/source links while
   removing local path metadata or other sensitive contents. The private bundle
   above makes this review concrete; its original bytes still expose local paths.
   The sanitized candidate now recomputes the path-independent paper tables,
   and a separate local audit verified its byte link to the private original.
   This does not establish privacy suitability or an external access route for
   reviewers.
4. Record the final paper/source revision and archive the exact manuscript,
   analysis code, frozen historical receipt list, raw input hashes, and any released
   dataset identifier together. Re-run the commands in [`README.md`](README.md)
   against that final package.
5. Review the scientific positioning: the historical audit has five selected
   families and one run per arm. The separate v7 pilot has two authored families
   and three seed repetitions per cell; its six matched C3/C4 blocks showed no
   reduction in submissions under truthful contradiction feedback, while one
   selected secure-onset fork took one decision after truthful PASS versus three
   after false FAIL. Neither result warrants a population effect or confidence
   interval. A general causal or rational-stopping claim requires the separately
   gated prospective study and independently validated observations.

## Reproduction check on this workspace

On 5 October 2026, `analysis.paper_pipeline` completed with 40 historical main
episodes, eight separate AEAD pilot episodes, 101 frozen historical receipts,
16 accepted repairable final candidates, and nine test–gate disagreements in
the nominally unavailable group. The separate v7 audit verified 30/30
prescheduled pilot episodes; its matched-fork audit verified both continuations.
The source-fidelity audit verified 77 source entries, 37 adjacent pairs, and
the archive-to-live-log byte links. `paper.build_submission` regenerated the
identified 16-page and anonymous 15-page PDFs, paired DOCX files, six figures,
and four tables. These checks validate this workspace's saved artifacts, not
an independent third-party replication. The current manuscript and decisions
form is hash-bound to these rendered copies. On 8 October 2026, the separate
original-byte audit verified 313 original members, 312 transformed counterparts,
and the original terminal 9/20 count, while reporting one current input-ledger
digest drift. The v6 author-review bundle was built and verified after these
edits; final author and venue decisions remain pending.
