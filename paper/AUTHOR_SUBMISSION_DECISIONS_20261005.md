# Author submission decision record — pending

This record identifies the exact exploratory manuscript files for **local author
review**. It does not approve journal submission, a journal data deposit, or the scientific
claims. The author supplied his name, location, and contact in this conversation;
funding, conflicts, acknowledgments, and other declarations will be clarified
separately. Do not infer their absence from a missing response.

## Exact draft under review

| Artifact | Current SHA-256 |
| --- | --- |
| [`final.md`](final.md) | `71de04936dc99ea8169c248a3742872b89a18ed89ff8e707c7910be2c2a6a572` |
| [Identified `full_paper.pdf`](submission/full_paper.pdf) | `2212e03ec77f66ffebbbfca8481514807258a0105a08f1410387855448a1f502` |
| [Identified `full_paper.docx`](submission/full_paper.docx) | `fe9be94e57bef198f8d60445ad03993f9ae20ebd8f4916afb191417d0c89f703` |
| [Anonymous `full_paper_anonymous.pdf`](submission/full_paper_anonymous.pdf) | `942eedc00d6586e58ca472ed1d1cc9c240875619c76077c0727b46a0a9d8bc95` |
| [Anonymous `full_paper_anonymous.docx`](submission/full_paper_anonymous.docx) | `238dca97d1da5ee262992010d4944fd023e9cd058998861aa410fd589ea2be73` |
| [`results.json`](artifacts/results.json) | `3d7ef25bfa07ef25ae20cea8d6ee34b59c5d9158e20c2e9b7013bfbd5a3cb229` |
| [Working author-year conversion](venue_author_year_draft.md) | `3194eefc193663633349ed25e28b06b4b469a58ab27c94abdf8908b2d2fbddc0` |
| [Venue shortlist](VENUE_SHORTLIST_20261005.md) | `6946eda6d419aa0d08ec245c9545d49951902789013e45cd1d7999991138a133` |

The identified and anonymous PDFs each have 16 A4 pages. PDF text,
including captions and tables, is 12 pt;
the DOCX styles are 12 pt with single line spacing. The abstract has 237 words
and the article contains six figures and four tables. The identified and
anonymous PDF/DOCX pairs regenerated with identical hashes on this workspace.
The anonymous files have blank author metadata and automated scans found no
author name, contact, location, or study-commit marker in their content. Word
page count and final venue compliance must be checked in the journal's editor.

These hashes identify this review draft only. Recompute them and repeat
scientific review after any manuscript, analysis, or rendering change. The
final reviewed source revision and exact data package must be recorded together.
The author-year conversion is a working venue adaptation and is not the
rendered PDF/DOCX or an approved final submission file.

## Decisions to record

| Decision | Required human entry | Current status |
| --- | --- | --- |
| Venue | Journal/conference, article type, checked author guidelines and date | `PENDING` |
| Authors and contact | Ordered full names, affiliation and corresponding author | `PARTIAL`: Imran Zakirov; independent student researcher without institutional affiliation; Bishkek, Kyrgyzstan; zakirovimran333@gmail.com. Sole authorship and wording need final author approval. |
| Contributions | Approved contribution statement from all named authors | `PENDING` |
| Declarations | Funding, conflicts, acknowledgments, ethics and required AI-tool disclosure | `PENDING`: author said details will follow separately. Known Codex assistance is disclosed in Methods and Acknowledgments for author review; the author must confirm the final wording. |
| Scientific sign-off | Authors approve the exact exploratory claims and limitations in the hashed draft | `PENDING` |
| Data route | Exact public source revision and journal-accepted data statement or supplementary deposit | `PARTIAL`: the author chose GitHub publication of the raw experimental artifacts; data revision [`37074c198237ade67eb76921333b2835d329c863`](https://github.com/Imranqsl212/AiResearch/tree/37074c198237ade67eb76921333b2835d329c863) is recorded. Journal route and persistent identifier are pending. |
| Privacy sign-off | Human review of raw and transformed free text, with disposition of residual candidates | `PENDING`: GitHub tracks unredacted archives and a review packet; suitability for a journal deposit is not established. |
| Final package | Venue formatting, final hashes, source revision, supplementary files, cover letter and submission account | `PENDING` |

The current sanitized review candidate has SHA-256
`48720a5620a1437094268452caab8f0168516454166147e575dea1c1039c0dd3`.
A [separate local original-byte audit](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md)
verified all 313 original archive members against the sanitized manifest and
recounted the central **9/20** result from the original terminal receipts.
This establishes a local archive-to-archive byte link, not an external chain
of custody, rerun of the evaluator, privacy clearance, or journal-deposit approval.
The archived private inventory's input-ledger digest differs from the current
tracked `artifacts/input_hashes.csv`: 308 of 311 input member hashes match.
The three differing digests are `analysis/paper_pipeline.py`,
`docs/OVERNIGHT_PROFILE.md`, and `experiments/executable_episode.py` after
later workspace versions. The original ledger CSV bytes were not archived as a member;
do not label the current CSV as that exact historical ledger.
Its [inspection report](../experiments/runs/paper_sanitized_privacy_packet_20261005_v2/PRIVATE_INSPECTION_REPORT.json), tracked on GitHub,
has SHA-256
`efc747fec81e94b972a408cc496e22702969eb477ca2917164687df2654c4841`.
The report lists eight remaining path candidates and 457 lexical review
leads. Those numbers are a review worklist, not clearance; the report and
archive are not approved supplements.

See the [submission handoff](SUBMISSION_HANDOFF_20261005.md),
[data-availability options](DATA_AVAILABILITY_OPTIONS_20261005.md), and
[venue shortlist](VENUE_SHORTLIST_20261005.md). This local form includes author
identity and must not be uploaded as an anonymous peer-review supplement.
