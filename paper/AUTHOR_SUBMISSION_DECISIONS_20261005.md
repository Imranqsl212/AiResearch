# Author submission decision record — pending

This record identifies the exact exploratory manuscript files for **local author
review**. It does not approve journal submission, data release, or the scientific
claims. The author supplied his name, location, and contact in this conversation;
funding, conflicts, acknowledgments, and other declarations will be clarified
separately. Do not infer their absence from a missing response.

## Exact draft under review

| Artifact | Current SHA-256 |
| --- | --- |
| [`final.md`](final.md) | `f8b167252eb7f06d547768bb16292673bddd542b4a6af4d93f2daa9aff2c949f` |
| [Identified `full_paper.pdf`](submission/full_paper.pdf) | `9ff2101a5b266e573e3c7404eedb46efc3e9a0fdcc44916edc0cbe02be2db621` |
| [Identified `full_paper.docx`](submission/full_paper.docx) | `c644765c009184f1acdfb0e58de2902f1937f78aaca4cd5dbbf6c4460b3c885f` |
| [Anonymous `full_paper_anonymous.pdf`](submission/full_paper_anonymous.pdf) | `cf441273640fd14d429cb36647458c0ee60eab45738ea45371079bfe6186e7ca` |
| [Anonymous `full_paper_anonymous.docx`](submission/full_paper_anonymous.docx) | `5b575416742753dcc515210b84f67f3c1758ef77c1951c346b35afd554e240fc` |
| [`results.json`](artifacts/results.json) | `3d7ef25bfa07ef25ae20cea8d6ee34b59c5d9158e20c2e9b7013bfbd5a3cb229` |

The identified PDF has 16 A4 pages and the anonymous PDF has 15. PDF text,
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

## Decisions to record

| Decision | Required human entry | Current status |
| --- | --- | --- |
| Venue | Journal/conference, article type, checked author guidelines and date | `PENDING` |
| Authors and contact | Ordered full names, affiliation and corresponding author | `PARTIAL`: Imran Zakirov; independent student researcher without institutional affiliation; Bishkek, Kyrgyzstan; zakirovimran333@gmail.com. Sole authorship and wording need final author approval. |
| Contributions | Approved contribution statement from all named authors | `PENDING` |
| Declarations | Funding, conflicts, acknowledgments, ethics and required AI-tool disclosure | `PENDING`: author said details will follow separately. Known Codex assistance is disclosed in Methods and Acknowledgments for author review; the author must confirm the final wording. |
| Scientific sign-off | Authors approve the exact exploratory claims and limitations in the hashed draft | `PENDING` |
| Data route | Actual public deposit, approved controlled-access procedure, or journal-approved exception, with location/custodian | `PENDING` |
| Privacy sign-off | Human review of the sanitized archive and all free text, with disposition of residual candidates | `PENDING` |
| Final package | Venue formatting, final hashes, source revision, supplementary files, cover letter and submission account | `PENDING` |

The current sanitized review candidate has SHA-256
`48720a5620a1437094268452caab8f0168516454166147e575dea1c1039c0dd3`.
A [separate local original-byte audit](ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md)
verified all 313 original archive members against the sanitized manifest and
recounted the central **9/20** result from the original terminal receipts.
This establishes a local archive-to-archive byte link, not an external chain
of custody, rerun of the evaluator, privacy clearance, or release approval.
The archived private inventory's input-ledger digest differs from the current
tracked `artifacts/input_hashes.csv`: 310 of 311 input member hashes match,
while the `experiments/executable_episode.py` digest differs after a later
workspace version. The original ledger CSV bytes were not archived as a member;
do not label the current CSV as that exact historical ledger.
Its Git-ignored [private inspection report](../experiments/runs/paper_sanitized_privacy_packet_20261005_v2/PRIVATE_INSPECTION_REPORT.json)
has SHA-256
`efc747fec81e94b972a408cc496e22702969eb477ca2917164687df2654c4841`.
The report lists eight remaining path candidates and 457 lexical review
leads. Those numbers are a review worklist, not clearance; the report and
archive are not approved supplements.

See the [submission handoff](SUBMISSION_HANDOFF_20261005.md),
[data-availability options](DATA_AVAILABILITY_OPTIONS_20261005.md), and
[venue shortlist](VENUE_SHORTLIST_20261005.md). This local form includes author
identity and must not be uploaded as an anonymous peer-review supplement.
