# Author submission decision record — pending

This record identifies the exact exploratory manuscript files for **local author
review**. It does not approve journal submission, a journal data deposit, or the scientific
claims. The author supplied his name, location, and contact in this conversation;
funding, conflicts, acknowledgments, and other declarations will be clarified
separately. Do not infer their absence from a missing response.

## Exact draft under review

| Artifact | Current SHA-256 |
| --- | --- |
| [`final.md`](final.md) | `44b2583583dd245deeebfb399a259796e0861e931817afd0f918b77464564546` |
| [Identified `full_paper.pdf`](submission/full_paper.pdf) | `d41b536071595f208e4eaabf725cf6db7d8d2f762fb42cf78d06724bad89c336` |
| [Identified `full_paper.docx`](submission/full_paper.docx) | `fbbf1130c3ebe4fc9044dd03bb7ad5d6c21960bfab1850afee247b4536ce3787` |
| [Anonymous `full_paper_anonymous.pdf`](submission/full_paper_anonymous.pdf) | `32baf373bbf1696eda9bec80feaecb2f0a70f5cb05a748165e3d9aaa8d84cd08` |
| [Anonymous `full_paper_anonymous.docx`](submission/full_paper_anonymous.docx) | `a4ebc3dcb4967e4a64a0326bfdaf3b9557514f1eb8fc26c9ec7969d5c93ed5e1` |
| [`results.json`](artifacts/results.json) | `3d7ef25bfa07ef25ae20cea8d6ee34b59c5d9158e20c2e9b7013bfbd5a3cb229` |

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
tracked `artifacts/input_hashes.csv`: 310 of 311 input member hashes match,
while the `experiments/executable_episode.py` digest differs after a later
workspace version. The original ledger CSV bytes were not archived as a member;
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
