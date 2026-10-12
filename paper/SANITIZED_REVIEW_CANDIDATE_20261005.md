# Historical paper bundle: sanitized review candidate

**Status: `REVIEW_ONLY_SANITIZED_CANDIDATE`.** This is an inspection copy of
the historical exploratory paper inputs. A separate table-only replay from its
transformed bytes now matches the saved paper results. It is not the original
raw dataset or an approved public supplement. It contains
the completed historical cohort described in `paper/final.md`; it does not turn
the later C1–C5 pilots into confirmatory data. The archives are tracked in the
current research branch; Git availability does not establish privacy review
or journal supplement approval.

## Exact files and hash relationship

| Item | SHA-256 | Role |
| --- | --- | --- |
| `experiments/runs/paper_private_repro_inputs_20261005.tar.gz` | `39ded8a4301ba0ebb193b48d71b032b0127a521c381fa378c67d08132319fc26` | Original private archive, left untouched. |
| `experiments/runs/paper_sanitized_review_candidate_20261005.tar.gz` | `48720a5620a1437094268452caab8f0168516454166147e575dea1c1039c0dd3` | Tracked transformed review copy. |
| `SANITIZATION_MANIFEST.json` inside the review copy | `a53a24fedc8f0a9f4fce2bf7d4451ebcb62cd06fc8de1d3b8ae465fc74dffef7` | Per-member original-to-transformed SHA-256 and byte-count map. |

The private archive has 313 members, including its `BUNDLE_INVENTORY.json`.
The review copy has 314 members. It replaces that old inventory with
`SANITIZATION_MANIFEST.json` and adds `REVIEW_ONLY_NOTICE.txt`. Of the 312
source data members, **200 changed bytes**. The manifest retains each original
member hash and its transformed hash; the old inventory's original hash is
recorded with no transformed member. The original archive and its sidecar receipt
were neither rewritten nor rehashed to disguise these changes.

The transformation substitutes the research root, host home and temporary
directories, and the discovered local account token with explicit markers. JSON
and JSONL members parse after transformation, with JSONL record counts preserved.
Those checks are structural only: paths inside observations, embedded hashes,
receipts, and task events may have changed meaning. The transformed archive is
**not byte-identical raw data**. Its original historical hash chain cannot be
revalidated from changed bytes. A separate recomputation path for the
path-independent paper tables is described below.

## Scanner result and limits

The targeted scanner found zero residual occurrences of the discovered local
username, macOS/Linux home paths, macOS volume paths, Unix temporary paths, or
Windows user-home paths in archive member names and contents. A broader lexical
scan found 800 multi-segment POSIX path candidates in 187 files. Of these, 792
follow the `<RESEARCH_ROOT>` placeholder; the eight others are one traversal
example, three `/usr` code/environment examples, one `/opt` runtime path, and
three `/training` synthetic task paths. These eight still require human content
review. The scanner is not a complete privacy audit: it does not decide whether
free text, names unrelated to the discovered account token, secrets, or other
metadata are safe to publish.

A [private inspection packet](../experiments/runs/paper_sanitized_privacy_packet_20261005_v2/PRIVATE_INSPECTION_REPORT.json)
now records the exact member, byte offset, line, and bounded context for all
eight residual path candidates. A conservative lexical pass adds 457 review
leads across the transformed archive, including possible names, addresses,
credential labels, URLs, redaction markers, and model-deliberation tags. These
are leads rather than verified sensitive data. The tracked report has
mode `0600` (directory `0700`) and SHA-256
`efc747fec81e94b972a408cc496e22702969eb477ca2917164687df2654c4841`.
Its metadata still mark it private, and it records `human_privacy_review_complete=false` and
`public_release_approved=false`. No raw snippets are placed in this document.

Run the offline checks from the repository root:

```sh
python3 -B -m paper.build_sanitized_review_bundle verify
python3 -B -m paper.build_sanitized_review_bundle scan
python3 -B -m unittest paper.test_sanitized_review_bundle -v
python3 -B -m paper.build_sanitized_privacy_packet
python3 -B -m unittest paper.test_sanitized_privacy_packet -v
```

`paper.build_sanitized_review_bundle build` creates a new review archive only
when that output and its receipt do not already exist. The code reads tar members
in memory without extracting them. The new sidecar receipt is
`experiments/runs/paper_sanitized_review_candidate_20261005.tar.receipt.json`.

## Table-only replay from transformed bytes

[`replay_sanitized_candidate.py`](replay_sanitized_candidate.py) reads the
sanitized archive, tracked `artifacts/results.json` and
`artifacts/source_api_inventory.csv`. It does **not** read the private original
archive. It checks the new hash of every transformed member, reconstructs
40 main and eight pilot episode summaries, and matches all 86 submitted source
hashes and API inventories. It recomputes 13 saved result sections, including
the numerical inputs to Tables 1–3, all four exploratory contrasts and the
101-receipt historical cohort/outcome counts. The 13 sections matched the
tracked results. The [local candidate receipt](../experiments/runs/paper_sanitized_table_replay_candidate_20261005.json)
has SHA-256
`83bdf413097d4d68a8697cd229a0ac01a077e299af7174ef24a38536b902fdc0`.

```sh
python3 -B -m paper.replay_sanitized_candidate
python3 -B -m unittest paper.test_replay_sanitized_candidate -q
```

The replay uses the tracked `analysis.paper_pipeline` summary functions and
checks that their source bytes match the archived analysis copy. It is a
deterministic re-analysis from transformed records, not an independent
implementation of the statistics. It does not rerun the original per-run hash
validator, prove source commit or safety attestation, render the PDF, or
execute the model/evaluator. The original private archive remains necessary
for original-byte provenance checks. The older sanitizer's structural verifier
still returns `REVIEW_ONLY_VERIFIED_NOT_REPLAY_READY`; that status refers to the
original hash chain, while the new script reports the narrower table replay.

## Release gate

A release still needs human privacy review, a documented decision about the
remaining path-like strings and sensitive free text, an agreed treatment of the
original-byte provenance gap, and a data-availability statement matching the
actual access route. The table-only replay is available for author review;
it does not establish privacy clearance or journal data-release approval.
The original and sanitized candidate are tracked in this branch, including
material whose review decisions remain open.
