"""Build a small, deterministic, REVIEW_ONLY manuscript package.

This is a filtered copy of derived manuscript files for local author review.
It contains no raw trajectory, model response, or sanitized replay archive.
The package preserves each selected source file byte for byte and records its
SHA-256; it does not establish original-run provenance or release clearance.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
V1_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261005_v1.tar.gz"
V2_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261005_v2.tar.gz"
V3_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261005_v3.tar.gz"
V4_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261005_v4.tar.gz"
V5_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261008_v5.tar.gz"
V6_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261008_v6.tar.gz"
V7_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261012_v7.tar.gz"
V8_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261012_v8.tar.gz"
V9_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261016_v9.tar.gz"
V10_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261016_v10.tar.gz"
V11_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261101_v11.tar.gz"
V12_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261101_v12.tar.gz"
V13_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261104_v13.tar.gz"
V14_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261104_v14.tar.gz"
V15_OUTPUT = ROOT / "experiments/runs/paper_author_review_manuscript_20261104_v15.tar.gz"
OUTPUT = V11_OUTPUT
V1_VERSION = "paper-author-review-manuscript-1.0.0"
V2_VERSION = "paper-author-review-manuscript-2.0.0"
V3_VERSION = "paper-author-review-manuscript-3.0.0"
V4_VERSION = "paper-author-review-manuscript-4.0.0"
V5_VERSION = "paper-author-review-manuscript-5.0.0"
V6_VERSION = "paper-author-review-manuscript-6.0.0"
V7_VERSION = "paper-author-review-manuscript-7.0.0"
V8_VERSION = "paper-author-review-manuscript-8.0.0"
V9_VERSION = "paper-author-review-manuscript-9.0.0"
V10_VERSION = "paper-author-review-manuscript-10.0.0"
V11_VERSION = "paper-author-review-manuscript-11.0.0"
V12_VERSION = "paper-author-review-manuscript-12.0.0"
V13_VERSION = "paper-author-review-manuscript-13.0.0"
V14_VERSION = "paper-author-review-manuscript-14.0.0"
V15_VERSION = "paper-author-review-manuscript-15.0.0"
VERSION = V11_VERSION
README_NAME = "REVIEW_ONLY_README.md"
MANIFEST_NAME = "SOURCE_HASH_MANIFEST.json"
V1_SOURCE_NAMES = (
    "paper/final.md",
    "paper/submission/full_paper.pdf",
    "paper/submission/full_paper.docx",
    "paper/submission/cover_letter_template.md",
    "paper/references.bib",
    "paper/figures/figure1_family_acceptance.png",
    "paper/figures/figure2_actions.png",
    "paper/figures/figure3_source_pairs.png",
    "paper/figures/figure4_stopping.png",
    "paper/figures/figure5_claims.png",
    "paper/figures/figure6_timelines.png",
    "paper/artifacts/arm_summary.csv",
    "paper/artifacts/condition_summary.csv",
    "paper/artifacts/exploratory_contrasts.csv",
    "paper/artifacts/family_summary.csv",
    "paper/artifacts/historical_inventory.csv",
    "paper/artifacts/input_hashes.csv",
    "paper/artifacts/run_metrics.csv",
    "paper/artifacts/source_api_inventory.csv",
    "paper/artifacts/results.json",
    "paper/DATA_AVAILABILITY_OPTIONS_20261005.md",
    "paper/AUTHOR_SUBMISSION_DECISIONS_20261005.md",
)
V2_SOURCE_NAMES = V1_SOURCE_NAMES + (
    "paper/submission/full_paper_anonymous.pdf",
    "paper/submission/full_paper_anonymous.docx",
)
V3_SOURCE_NAMES = V2_SOURCE_NAMES + (
    "analysis/source_fidelity_v1.json",
    "analysis/v7_decisive_excluded_audit_20261005.json",
    "analysis/v7_decisive_c5_fork_audit_20261005.json",
    "paper/STRATEGY_CODING_PROTOCOL_20261005.md",
    "docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md",
)
V4_SOURCE_NAMES = V3_SOURCE_NAMES
V5_SOURCE_NAMES = V4_SOURCE_NAMES + (
    "paper/independent_discordance_check.py",
    "paper/test_independent_discordance_check.py",
    "paper/INDEPENDENT_DISCORDANCE_CHECK_20261008.md",
)
V6_SOURCE_NAMES = V5_SOURCE_NAMES + (
    "paper/audit_original_archive_provenance.py",
    "paper/test_audit_original_archive_provenance.py",
    "paper/ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md",
)
V7_SOURCE_NAMES = V6_SOURCE_NAMES
V8_SOURCE_NAMES = V7_SOURCE_NAMES
V9_SOURCE_NAMES = V8_SOURCE_NAMES
V10_SOURCE_NAMES = V9_SOURCE_NAMES + (
    "paper/venue_author_year_draft.md",
    "paper/VENUE_SHORTLIST_20261005.md",
)
V11_SOURCE_NAMES = V10_SOURCE_NAMES + (
    "paper/submission/venue_author_year_identified.pdf",
    "paper/submission/venue_author_year_identified.docx",
    "paper/submission/venue_author_year_anonymous.pdf",
    "paper/submission/venue_author_year_anonymous.docx",
    "analysis/C5_PAIRED_REGRESSION_RECOUNT_20261101.md",
    "analysis/c5_paired_regression_recount_20261101.json",
    "analysis/C5_CANDIDATE_DISCORDANCE_20261101.md",
    "analysis/c5_candidate_discordance_20261101.json",
    "analysis/FRESH_MATCHED_VERDICT_PILOT_20261101.md",
    "analysis/fresh_matched_verdict_pilot_20261101.json",
    "analysis/V7_SECOND_WAVE_20261101.md",
    "analysis/v7_second_wave_20261101.json",
)
V12_SOURCE_NAMES = V11_SOURCE_NAMES + (
    "analysis/V7_TEMP_VARIANCE_20261101.md",
    "analysis/v7_temp_variance_20261101.json",
    "analysis/V7_TEMP_VARIANCE_SECONDWAVE_20261101.md",
    "analysis/v7_temp_variance_secondwave_20261101.json",
    "analysis/HISTORICAL_MATCHED_SOURCE_FEEDBACK_20261104.md",
    "analysis/historical_matched_source_feedback_20261104.json",
    "analysis/C5_FEEDBACK_ACTION_20261104.md",
    "analysis/c5_feedback_action_20261104.json",
    "analysis/figures/v7_temp03_pair_outcomes_20261101.png",
)
V13_SOURCE_NAMES = V12_SOURCE_NAMES
V14_NEW_DERIVED = (
    "analysis/HISTORICAL_FEEDBACK_SPECIFICITY_20261104.md",
    "analysis/historical_feedback_specificity_20261104.json",
    "analysis/C5_FIRST_SUBMISSION_PARITY_20261104.md",
    "analysis/c5_first_submission_parity_20261104.json",
    "analysis/V7_LEAVE_ONE_WORLD_OUT_20261104.md",
    "analysis/v7_leave_one_world_out_20261104.json",
    "analysis/V7_CROSSFAMILY_ERROR_DIRECTION_20261104.md",
    "analysis/v7_crossfamily_error_direction_20261104.json",
    "analysis/V7_CSRF_TRANSITION_DIRECTION_20261104.md",
    "analysis/v7_csrf_transition_direction_20261104.json",
    "analysis/V7_TEMP03_ERROR_DIRECTION_20261104.md",
    "analysis/v7_temp03_error_direction_20261104.json",
    "analysis/LOGGED_SOURCE_SURROGATE_AST_20261104.md",
    "analysis/logged_source_surrogate_ast_20261104.json",
    "docs/EXCLUDED_V7_CROSSFAMILY_20261104_RESULTS.md",
    "analysis/v7_crossfamily_20261104.json",
    "docs/EXCLUDED_V7_FEEDBACK_REPLICATION_20261104_RESULTS.md",
    "analysis/v7_feedback_replication_20261104.json",
)
V14_SOURCE_NAMES = V13_SOURCE_NAMES + V14_NEW_DERIVED
V15_NEW_DERIVED = (
    "analysis/HISTORICAL_PROTOCOL_STOP_RECOUNT_20261104.md",
    "analysis/historical_protocol_stop_recount_20261104.json",
    "analysis/V7_ENDPOINT_SENSITIVITY_20261104.md",
    "analysis/v7_endpoint_sensitivity_20261104.json",
    "analysis/V7_TEST_SET_SUFFICIENCY_20261104.md",
    "analysis/v7_test_set_sufficiency_20261104.json",
    "analysis/V7_GEMMA_TRANSFER_20261104.md",
    "analysis/v7_gemma_transfer_20261104.json",
    "analysis/v7_gemma_transfer_20261104_screen.json",
    "figures/v7_checker_stage_cascade_20261104.svg",
)
V15_SOURCE_NAMES = V14_SOURCE_NAMES + V15_NEW_DERIVED
SOURCE_NAMES = V11_SOURCE_NAMES
FORBIDDEN_MARKERS = {
    "mac_home": re.compile(rb"/Users/[^/\s\"'<>\\]+", re.I),
    "linux_home": re.compile(rb"/home/[^/\s\"'<>\\]+", re.I),
    "mac_temp": re.compile(rb"/private/var/folders/[^\s\"'<>\\]+", re.I),
    "windows_home": re.compile(rb"[A-Za-z]:\\Users\\[^\s\"'<>]+", re.I),
}
MAX_MEMBER_BYTES = 8_000_000
MAX_TOTAL_BYTES = 32_000_000
PUBLIC_DATA_REVISION = "37074c198237ade67eb76921333b2835d329c863"

V1_README = """# Local author-review manuscript bundle

**Status: REVIEW_ONLY. Public release and journal submission are not approved.**

This package contains exact copies of the current exploratory manuscript,
rendered PDF and DOCX, six figures, references, derived result tables, the
cover-letter template, data-availability options, and the author decision form.
`SOURCE_HASH_MANIFEST.json` records each selected source file's SHA-256 and byte
count. `paper/artifacts/input_hashes.csv` is the paper's historical input
ledger; the inputs named there are **not** included in this package.

The package deliberately excludes raw trajectories, original responses,
private source snapshots, the private original-byte archive, the sanitized
review candidate, and unrelated historical JSON. It cannot reproduce the
historical numbers from original trajectories by itself. Its derived tables
and source hashes support author inspection, not an independent replay of
the original evidence chain. The author decision form records open scientific,
privacy, venue, identity, declaration, and data-access decisions.

The builder rejects selected files containing a small set of local home-path
and account markers. This automated screen does not clear free text, metadata,
images, privacy, or scientific validity. Authors must review the exact files
and choose an approved data route before any external distribution.

Verify against the local source tree with:

    python3 -B -m paper.build_author_review_bundle verify \\
      --archive experiments/runs/paper_author_review_manuscript_20261005_v1.tar.gz

No Git commit, model run, raw-data replay, independent timestamp, or digital
signature is bound to this archive. The SHA-256 receipt identifies the local
package bytes and detects accidental changes when checked against a trusted
copy of that receipt.
"""

V2_README = """# Local author-review manuscript bundle v2

**Status: REVIEW_ONLY. Public release and journal submission are not approved.**

This package contains exact copies of the current exploratory manuscript,
identified and anonymous PDF/DOCX files, six figures, references, derived
result tables, the cover-letter template, data-availability options, and the
author decision form. `SOURCE_HASH_MANIFEST.json` records each selected source
file's SHA-256 and byte count. `paper/artifacts/input_hashes.csv` is the paper's
historical input ledger; those raw inputs are **not** included here.

The package excludes raw trajectories, original responses, private source
snapshots, the private original-byte archive, the sanitized review candidate,
and unrelated historical JSON. It cannot reproduce historical numbers from
original trajectories by itself. The author decision form binds the manuscript,
both rendered file pairs, and derived results by hash, while recording pending
scientific, privacy, venue, identity, declaration, and data-access decisions.

The anonymous files are drafts for peer review. The builder screens selected
bytes and expanded DOCX members for a small set of local home-path and account
markers. This automated screen does not clear free text, metadata, images,
privacy, or scientific validity. Authors must review exact files and choose
an approved data route before any external distribution.

Verify against the local source tree with:

    python3 -B -m paper.build_author_review_bundle verify \\
      --archive experiments/runs/paper_author_review_manuscript_20261005_v2.tar.gz

Use `--no-local-compare` to verify the archived bytes and receipt after the
workspace sources have changed. No Git commit, model run, raw-data replay,
independent timestamp, or digital signature is bound to this archive. The
SHA-256 receipt detects accidental changes only when checked against a trusted
copy of that receipt.
"""
V3_README = """# Local author-review manuscript bundle v3

**Status: REVIEW_ONLY. Public release and journal submission are not approved.**

This package contains exact copies of the revised exploratory manuscript,
identified and anonymous PDF/DOCX files, six figures, historical derived
tables, and separate derived audits for the excluded 30-episode corrected-
oracle pilot and its one matched continuation. It also includes the source-
fidelity inventory, a proposed strategy-coding protocol, references, the
cover-letter template, data-availability options, and the author decision
form. The pilot is not pooled with the historical 40-episode denominator.

`SOURCE_HASH_MANIFEST.json` records each selected file's SHA-256 and byte
count. `paper/artifacts/input_hashes.csv` is the historical input ledger;
the original raw inputs, local pilot trajectories, source snapshots, model
responses, private archives, and sanitized candidate are not included.
This package cannot reproduce the original-run or pilot evidence chains from
raw traces by itself. The author decision form binds the current manuscript,
rendered pairs, and historical derived results by hash. All scientific,
privacy, venue, identity, declaration, and data-access decisions remain open.

The builder screens selected bytes and expanded DOCX members for a small set
of local path and account markers. This does not establish privacy clearance
for all free text, metadata, images, or scientific validity. The anonymous
copies are review drafts, not approved submissions.

Verify against the local source tree with:

    python3 -B -m paper.build_author_review_bundle verify \\
      --archive experiments/runs/paper_author_review_manuscript_20261005_v3.tar.gz

Use `--no-local-compare` to verify archived bytes and receipt after the
workspace changes. No final Git revision, independent timestamp, or digital
signature is bound. The SHA-256 receipt detects accidental changes when
checked against a trusted copy.
"""
V4_README = V3_README.replace("bundle v3", "bundle v4").replace(
    "paper_author_review_manuscript_20261005_v3.tar.gz",
    "paper_author_review_manuscript_20261005_v4.tar.gz",
)
V5_README = V4_README.replace("bundle v4", "bundle v5").replace(
    "paper_author_review_manuscript_20261005_v4.tar.gz",
    "paper_author_review_manuscript_20261008_v5.tar.gz",
).replace(
    "The pilot is not pooled with the historical 40-episode denominator.",
    "The pilot is not pooled with the historical 40-episode denominator. "
    "A separate standard-library script independently recounts the central "
    "9/20 disagreement from the transformed terminal receipts; the sanitized "
    "archive needed to run it is not inside this package.",
)
V6_README = V5_README.replace("bundle v5", "bundle v6").replace(
    "paper_author_review_manuscript_20261008_v5.tar.gz",
    "paper_author_review_manuscript_20261008_v6.tar.gz",
).replace(
    "archive needed to run it is not inside this package.",
    "archive needed to run it is not inside this package. A second read-only "
    "script checked the local original-to-sanitized byte link and independently "
    "recounted 9/20 from original terminal receipts. Both archives remain "
    "private and absent from this package; no public release or journal "
    "submission is approved.",
)
V7_README = V6_README.replace("bundle v6", "bundle v7").replace(
    "paper_author_review_manuscript_20261008_v6.tar.gz",
    "paper_author_review_manuscript_20261012_v7.tar.gz",
).replace(
    "Public release and journal submission are not approved.",
    "This filtered package is not approved as a journal supplement or submission.",
).replace(
    "Both archives remain private and absent from this package; no public release or journal "
    "submission is approved.",
    "The archives are tracked separately in the research branch and absent "
    "from this filtered package; no journal submission is approved.",
).replace(
    "responses, private archives, and sanitized candidate are not included.",
    "responses, original archives, and sanitized candidate are not included.",
).replace(
    "All scientific,\nprivacy, venue, identity, declaration, and data-access decisions remain open.",
    "Scientific, privacy, venue, identity, declaration, and journal data-route "
    "decisions remain open.",
)
V8_README = """# Local author-review manuscript bundle v8

**Status: REVIEW_ONLY. This filtered package is not an approved journal
supplement or submission.**

This package contains exact copies of the corrected exploratory manuscript,
identified and anonymous PDF/DOCX files, six figures, references, historical
derived tables, and separate audits for the excluded corrected-oracle pilot.
It also contains the source-fidelity inventory, strategy-coding protocol,
cover-letter template, data-availability options, and author decision form.
The pilot is not pooled with the historical 40-episode denominator.

The manuscript corrects the interpretation of the hidden acceptance veto,
recorded stopping labels, logger-redacted source, and fixed family guidance.
Some historical derived artifacts retain exploratory calculations that the
current article omits or no longer interprets as population estimates. Those
artifacts preserve the earlier analysis record; their presence is not a claim
of statistical significance, verified stopping intent, or secure code.

`SOURCE_HASH_MANIFEST.json` records each selected source file's SHA-256 and byte
count. `paper/artifacts/input_hashes.csv` is the historical input ledger.
Raw trajectories, original responses, source snapshots, original archives,
and the sanitized review candidate are not inside this filtered package;
they are tracked separately. The included audit scripts need those separate
inputs for replay. This package alone cannot regenerate the reported results
from raw traces.

The builder screens selected bytes and expanded DOCX members for a small set
of local path and account markers. This does not establish privacy clearance
for all free text, metadata, images, or scientific validity. The anonymous
files are review drafts. Author decisions on claims, declarations, journal
data route, privacy, and venue requirements remain open.

Verify against the local source tree with:

    python3 -B -m paper.build_author_review_bundle verify \\
      --archive experiments/runs/paper_author_review_manuscript_20261012_v8.tar.gz

Use `--no-local-compare` to verify archived bytes and receipt after the
workspace changes. No final Git revision, independent timestamp, or digital
signature is bound to this package. A SHA-256 receipt detects accidental
changes when checked against a trusted copy.
"""
V9_README = V8_README.replace(
    "bundle v8", "bundle v9"
).replace(
    "paper_author_review_manuscript_20261012_v8.tar.gz",
    "paper_author_review_manuscript_20261016_v9.tar.gz",
).replace(
    "The manuscript corrects the interpretation of the hidden acceptance veto,",
    "The cover-letter template identifies the public GitHub data revision "
    "37074c198237ade67eb76921333b2835d329c863. Historical and pilot "
    "archives, analysis code, and derived tables are publicly tracked there. "
    "Its bracketed data-and-code paragraph still needs author review of "
    "journal wording and privacy before submission. This filtered review "
    "package itself is not an approved journal supplement. The cited data "
    "revision does not attest to this v9 package's contents.\n\n"
    "The manuscript corrects the interpretation of the hidden acceptance veto,",
)
V10_README = V9_README.replace(
    "bundle v9", "bundle v10"
).replace(
    "paper_author_review_manuscript_20261016_v9.tar.gz",
    "paper_author_review_manuscript_20261016_v10.tar.gz",
).replace(
    "this v9 package's contents", "this v10 package's contents",
).replace(
    "Verify against the local source tree with:",
    "The package also includes a venue author-year conversion draft and a "
    "dated venue shortlist. These are working review materials, not the "
    "rendered manuscript or proof of journal compliance. Verify citation "
    "metadata and venue requirements before submission. The manifest does "
    "not attest whether this review archive is on GitHub; it records the "
    "already public data revision separately.\n\n"
    "Verify against the local source tree with:",
)
V11_README = """# Local author-review manuscript bundle v11

**Status: REVIEW_ONLY. This filtered package is not an approved journal
supplement or submission.**

This package copies the updated exploratory manuscript, identified and
anonymous canonical and author-year PDF/DOCX files, six figures, historical
derived tables, references, and the pending author decision form. It adds
derived reports and JSON results for the excluded 14-pair persistent-veto
recount and two sequential one-shot v7 pilot waves. These cohorts have
different selection histories and protocols and are not pooled as an
inferential sample or with the historical 40-episode denominator.

`SOURCE_HASH_MANIFEST.json` records each selected file's SHA-256 and byte
count. Raw trajectories, original responses, candidate source, source
snapshots, original archives, and the sanitized review candidate are not
inside this package. The derived reports require separately tracked raw
archives and analysis code for independent replay; this package alone cannot
reproduce their counts from raw traces.

The recorded public Git revision belongs to an older historical data release.
The exact Git revision containing the new pilot archives is pending in this
review package. Git visibility, journal data route, privacy clearance, and
author approval are not attested by this bundle. The anonymous files remain
review drafts; the identified decision form must not accompany an anonymous
peer-review submission.

The builder screens selected bytes and expanded DOCX members for a small set
of local path and account markers. That is not a full privacy or scientific
validity review. Before external distribution, the author must inspect the
exact package and choose an accepted data route.

Verify against the local source tree with:

    python3 -B -m paper.build_author_review_bundle verify \\
      --archive experiments/runs/paper_author_review_manuscript_20261101_v11.tar.gz

Use `--no-local-compare` to verify archived bytes and receipt after the
workspace changes. This receipt is a digest, not an independent timestamp,
signature, final source revision, or journal approval.
"""
V12_README = """# Local author-review manuscript bundle v12

**Status: REVIEW_ONLY. This filtered package is not an approved journal
supplement or submission.**

This package copies the updated exploratory manuscript, identified and
anonymous canonical and author-year PDF/DOCX files, six figures, historical
derived tables, references, and the pending author decision form. It retains
the excluded persistent-veto and sequential one-shot v7 pilot reports from
v11 and adds a derived report and JSON for the temperature 0.3 variance
pilot. The temperature 0.3 pilot is excluded exploratory data with a
different protocol; it is not pooled with the temperature-zero cohorts and
does not support the main inference.

This revision also includes the separately stopped second temperature 0.3
wave, the matched-source historical feedback audit, the older C5 action
audit, and their two-panel descriptive figure. Each report states its own
denominator and missingness; the cohorts are not pooled.

`SOURCE_HASH_MANIFEST.json` records each selected file's SHA-256 and byte
count. Raw trajectories, original responses, candidate source, source
snapshots, original archives, and the sanitized review candidate are not
inside this package. The derived reports require separately tracked raw
archives and analysis code for independent replay; this package alone cannot
reproduce their counts from raw traces.

The manifest identifies an earlier historical release and a later related-data
review revision. This bundle does not attest to Git visibility, a final source revision,
journal data route, privacy clearance, or author approval. The anonymous
files remain review drafts; the identified decision form must not accompany
an anonymous peer-review submission.

The builder screens selected bytes and expanded DOCX members for a small set
of local path and account markers. That is not a full privacy or scientific
validity review. Before external distribution, the author must inspect the
exact package and choose an accepted data route.

Verify against the local source tree with:

    python3 -B -m paper.build_author_review_bundle verify --archive experiments/runs/paper_author_review_manuscript_20261101_v12.tar.gz

Use `--no-local-compare` to verify archived bytes and receipt after the
workspace changes. This receipt is a digest, not an independent timestamp,
signature, final source revision, or journal approval.
"""
V13_README = V12_README.replace(
    "bundle v12", "bundle v13"
).replace(
    "six figures, historical",
    "five article figures and the standalone stop-label chart, historical",
).replace(
    "paper_author_review_manuscript_20261101_v12.tar.gz",
    "paper_author_review_manuscript_20261104_v13.tar.gz",
)
V14_README = """# Local author-review manuscript bundle v14

**Status: REVIEW_ONLY. This filtered package is not an approved journal
supplement or submission.**

This package binds the current exploratory manuscript, identified and
anonymous canonical and author-year PDF/DOCX renderings, the article figures,
historical derived tables, references, and the pending author decision form.
It adds selected derived reports for the historical feedback audit, first
candidate parity, checker-world sensitivity, source-surrogate AST audit,
and directional error analyses. Two separately selected, excluded live
waves are represented by their reports and JSON recounts. The new six-slot
wave is not pooled with the earlier three-family pilot or the historical
main-study denominator.

`SOURCE_HASH_MANIFEST.json` records exact hashes and byte counts. Raw
trajectories, model requests and responses, candidate source, source snapshots,
and the public run archives are **not** inside this filtered package. Those
separately tracked archives and analysis code are required to replay the
derived findings. This package itself does not establish original-run
provenance, human task admission, author approval, privacy clearance, or a
journal-accepted data route. The newest live-wave data Git revision is
unbound in this bundle; the historical-data revision applies only to an
earlier release.

The anonymous files remain review drafts. The identified author decision
form must not accompany an anonymous peer-review submission. The builder
screens selected bytes and expanded DOCX members for a limited set of local
path and account markers; authors must still inspect the exact package.

Verify against the current local source tree with:

    python3 -B -m paper.build_author_review_bundle verify --bundle-version v14

Use `--no-local-compare` to verify archived bytes and receipt after workspace
sources change. This digest receipt is not an independent timestamp,
signature, final source revision, or journal approval.
"""
V15_README = """# Local author-review manuscript bundle v15

**Status: REVIEW_ONLY. This filtered package is not an approved journal
supplement or submission.**

This package binds the current exploratory manuscript, identified and
anonymous PDF/DOCX renderings, article figures, historical derived tables,
references, and pending author decision form. It retains the v14 analyses
and adds derived reports/JSON for historical protocol stops, sensitivity to
the endpoint definition, and finite test-set sufficiency. It also includes
a descriptive checker-stage SVG and a screened excluded Gemma transfer-pilot
report/JSON. In Gemma's four fixed slots no secure precursor onset occurred,
so no matched feedback arms opened; this is not a measured transfer effect.

The bundle contains no raw trajectories, model requests/responses, source
snapshots, or separate run archives. Its source-hash manifest binds exact
selected bytes. Separately tracked archives and analysis code are needed to
replay findings. This filtered review package does not establish human task
admission, author approval, privacy clearance, a journal-accepted data route,
or a final Git revision for the newest material. The included screen receipt
is a limited pattern check, not a general privacy guarantee.

The anonymous files are review drafts. The identified decision form must
not accompany anonymous peer review. The builder screens selected bytes and
expanded DOCX members for limited local path and account markers; authors
must still inspect the exact package.

Verify against the current local source tree with:

    python3 -B -m paper.build_author_review_bundle verify --bundle-version v15

Use `--no-local-compare` to verify archived bytes and receipt after workspace
sources change. This digest receipt is not an independent timestamp,
signature, source revision, or journal approval.
"""
README = V11_README


@dataclass(frozen=True)
class BundleSpec:
    version: str
    source_names: tuple[str, ...]
    readme: str


V1_SPEC = BundleSpec(V1_VERSION, V1_SOURCE_NAMES, V1_README)
V2_SPEC = BundleSpec(V2_VERSION, V2_SOURCE_NAMES, V2_README)
V3_SPEC = BundleSpec(V3_VERSION, V3_SOURCE_NAMES, V3_README)
V4_SPEC = BundleSpec(V4_VERSION, V4_SOURCE_NAMES, V4_README)
V5_SPEC = BundleSpec(V5_VERSION, V5_SOURCE_NAMES, V5_README)
V6_SPEC = BundleSpec(V6_VERSION, V6_SOURCE_NAMES, V6_README)
V7_SPEC = BundleSpec(V7_VERSION, V7_SOURCE_NAMES, V7_README)
V8_SPEC = BundleSpec(V8_VERSION, V8_SOURCE_NAMES, V8_README)
V9_SPEC = BundleSpec(V9_VERSION, V9_SOURCE_NAMES, V9_README)
V10_SPEC = BundleSpec(V10_VERSION, V10_SOURCE_NAMES, V10_README)
V11_SPEC = BundleSpec(V11_VERSION, V11_SOURCE_NAMES, V11_README)
V12_SPEC = BundleSpec(V12_VERSION, V12_SOURCE_NAMES, V12_README)
V13_SPEC = BundleSpec(V13_VERSION, V13_SOURCE_NAMES, V13_README)
V14_SPEC = BundleSpec(V14_VERSION, V14_SOURCE_NAMES, V14_README)
V15_SPEC = BundleSpec(V15_VERSION, V15_SOURCE_NAMES, V15_README)
SPECS_BY_VERSION = {spec.version: spec for spec in
                    (V1_SPEC, V2_SPEC, V3_SPEC, V4_SPEC, V5_SPEC, V6_SPEC,
                     V7_SPEC, V8_SPEC, V9_SPEC, V10_SPEC, V11_SPEC, V12_SPEC,
                     V13_SPEC, V14_SPEC, V15_SPEC)}
BUILD_TARGETS = {"v11": (V11_OUTPUT, V11_SPEC), "v12": (V12_OUTPUT, V12_SPEC),
                 "v13": (V13_OUTPUT, V13_SPEC), "v14": (V14_OUTPUT, V14_SPEC),
                 "v15": (V15_OUTPUT, V15_SPEC)}


class BundleError(RuntimeError):
    """The review bundle fails an integrity or scope requirement."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _receipt_path(output: Path) -> Path:
    return output.with_suffix(".receipt.json")


def _screen(name: str, data: bytes) -> None:
    patterns = list(FORBIDDEN_MARKERS.values())
    candidates = [data]
    if name.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as document:
                if sum(member.file_size for member in document.infolist()) > MAX_TOTAL_BYTES:
                    raise BundleError("DOCX expanded members exceed byte limit")
                for member in document.infolist():
                    if member.file_size > MAX_MEMBER_BYTES:
                        raise BundleError("DOCX expanded member exceeds byte limit")
                    candidates.append(document.read(member))
        except (zipfile.BadZipFile, OSError) as exc:
            raise BundleError("DOCX is not a readable ZIP document") from exc
    for candidate in candidates:
        if any(pattern.search(candidate) for pattern in patterns):
            raise BundleError(f"host-specific marker in selected file: {name}")


def _decision_bound_names(spec: BundleSpec) -> tuple[str, ...]:
    names = (
        "paper/final.md",
        "paper/submission/full_paper.pdf",
        "paper/submission/full_paper.docx",
        "paper/artifacts/results.json",
    )
    if spec in (V2_SPEC, V3_SPEC, V4_SPEC, V5_SPEC, V6_SPEC, V7_SPEC, V8_SPEC, V9_SPEC, V10_SPEC, V11_SPEC, V12_SPEC, V13_SPEC, V14_SPEC, V15_SPEC):
        names += (
            "paper/submission/full_paper_anonymous.pdf",
            "paper/submission/full_paper_anonymous.docx",
        )
    if spec in (V10_SPEC, V11_SPEC, V12_SPEC, V13_SPEC, V14_SPEC, V15_SPEC):
        names += (
            "paper/venue_author_year_draft.md",
            "paper/VENUE_SHORTLIST_20261005.md",
        )
    if spec in (V11_SPEC, V12_SPEC, V13_SPEC, V14_SPEC, V15_SPEC):
        names += (
            "paper/submission/venue_author_year_identified.pdf",
            "paper/submission/venue_author_year_identified.docx",
            "paper/submission/venue_author_year_anonymous.pdf",
            "paper/submission/venue_author_year_anonymous.docx",
            "analysis/c5_paired_regression_recount_20261101.json",
            "analysis/c5_candidate_discordance_20261101.json",
            "analysis/fresh_matched_verdict_pilot_20261101.json",
            "analysis/v7_second_wave_20261101.json",
        )
    if spec in (V12_SPEC, V13_SPEC, V14_SPEC, V15_SPEC):
        names += (
            "analysis/V7_TEMP_VARIANCE_20261101.md",
            "analysis/v7_temp_variance_20261101.json",
            "analysis/V7_TEMP_VARIANCE_SECONDWAVE_20261101.md",
            "analysis/v7_temp_variance_secondwave_20261101.json",
            "analysis/HISTORICAL_MATCHED_SOURCE_FEEDBACK_20261104.md",
            "analysis/historical_matched_source_feedback_20261104.json",
            "analysis/C5_FEEDBACK_ACTION_20261104.md",
            "analysis/c5_feedback_action_20261104.json",
            "analysis/figures/v7_temp03_pair_outcomes_20261101.png",
        )
    if spec in (V14_SPEC, V15_SPEC):
        names += V14_NEW_DERIVED
    if spec is V15_SPEC:
        names += V15_NEW_DERIVED
    return names


def _check_decision_bindings(source: dict[str, bytes], spec: BundleSpec) -> None:
    try:
        decision = source["paper/AUTHOR_SUBMISSION_DECISIONS_20261005.md"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BundleError("author decision form is not UTF-8") from exc
    for name in _decision_bound_names(spec):
        if not any(Path(name).name in line and _sha(source[name]) in line
                   for line in decision.splitlines()):
            raise BundleError(f"author decision form does not identify current {name}")


def _source_bytes(spec: BundleSpec = V11_SPEC) -> dict[str, bytes]:
    if len(set(spec.source_names)) != len(spec.source_names):
        raise BundleError("duplicate source allowlist member")
    source: dict[str, bytes] = {}
    for name in spec.source_names:
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise BundleError(f"missing or symlinked source: {name}")
        data = path.read_bytes()
        if len(data) > MAX_MEMBER_BYTES:
            raise BundleError(f"selected file exceeds byte limit: {name}")
        _screen(name, data)
        source[name] = data
    if sum(map(len, source.values())) > MAX_TOTAL_BYTES:
        raise BundleError("selected files exceed bundle byte limit")
    _check_decision_bindings(source, spec)
    return source


def _release_flags(spec: BundleSpec) -> dict[str, Any]:
    if spec in (V14_SPEC, V15_SPEC):
        return {
            "journal_supplement_approved": False,
            "git_visibility": "not-attested-by-bundle",
            "related_data_public_git_revision": None,
            "historical_data_public_git_revision": PUBLIC_DATA_REVISION,
        }
    if spec in (V12_SPEC, V13_SPEC):
        return {
            "journal_supplement_approved": False,
            "git_visibility": "not-attested-by-bundle",
            "related_data_public_git_revision": "9ecd07a3d605cfd812a874835e9b945adc5d5145",
            "historical_data_public_git_revision": PUBLIC_DATA_REVISION,
        }
    if spec in (V11_SPEC, V12_SPEC, V13_SPEC, V14_SPEC, V15_SPEC):
        return {
            "journal_supplement_approved": False,
            "git_visibility": "not-attested-by-bundle",
            "related_data_public_git_revision": None,
            "historical_data_public_git_revision": PUBLIC_DATA_REVISION,
        }
    if spec is V10_SPEC:
        return {
            "journal_supplement_approved": False,
            "git_visibility": "not-attested-by-bundle",
            "related_data_public_git_revision": PUBLIC_DATA_REVISION,
        }
    return {"public_release_approved": False}


def _manifest(source: dict[str, bytes], readme: bytes, spec: BundleSpec = V11_SPEC) -> dict[str, Any]:
    return {
        "version": spec.version,
        "status": "REVIEW_ONLY",
        **_release_flags(spec),
        "journal_submission_approved": False,
        "original_raw_data_included": False,
        "original_byte_replay_verified": False,
        "source_git_revision_bound": False,
        "scope": "exploratory manuscript and derived tables for local author review",
        "files": [
            {"path": name, "sha256": _sha(source[name]), "bytes": len(source[name])}
            for name in sorted(source)
        ],
        "readme": {"path": README_NAME, "sha256": _sha(readme), "bytes": len(readme)},
    }


def _add(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(data))


def _archive_files(path: Path) -> dict[str, bytes]:
    if path.is_symlink() or not path.is_file():
        raise BundleError("archive is missing or symlinked")
    files: dict[str, bytes] = {}
    total = 0
    try:
        with tarfile.open(path, "r:gz") as archive:
            for member in archive:
                name = member.name
                if not member.isfile() or name in files or name.startswith("/") or ".." in Path(name).parts:
                    raise BundleError("archive contains unsafe, duplicate, or non-file member")
                if member.size > MAX_MEMBER_BYTES:
                    raise BundleError("archive member exceeds byte limit")
                stream = archive.extractfile(member)
                if stream is None:
                    raise BundleError("archive member cannot be read")
                data = stream.read(MAX_MEMBER_BYTES + 1)
                if len(data) != member.size:
                    raise BundleError("archive member byte count differs")
                total += len(data)
                if total > MAX_TOTAL_BYTES:
                    raise BundleError("archive exceeds byte limit")
                files[name] = data
    except (tarfile.TarError, OSError) as exc:
        raise BundleError("archive is unreadable") from exc
    return files


def verify(*, archive: Path = OUTPUT, compare_sources: bool = True) -> dict[str, Any]:
    archive = Path(archive)
    receipt_path = _receipt_path(archive)
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise BundleError("bundle receipt is missing or symlinked")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise BundleError("bundle receipt is unreadable") from exc
    if not isinstance(receipt, dict):
        raise BundleError("bundle receipt is invalid")
    spec = SPECS_BY_VERSION.get(receipt.get("version"))
    if spec is None:
        raise BundleError("unsupported review bundle version")
    digest = _sha(archive.read_bytes())
    if (receipt.get("archive_sha256") != digest or receipt.get("status") != "REVIEW_ONLY"
            or receipt.get("version") != spec.version
            or receipt.get("journal_submission_approved") is not False
            or receipt.get("archive_bytes") != archive.stat().st_size):
        raise BundleError("archive differs from review-only receipt")
    if (any(receipt.get(key) != value for key, value in _release_flags(spec).items())
            or (spec in (V10_SPEC, V11_SPEC, V12_SPEC, V13_SPEC, V14_SPEC, V15_SPEC) and "public_release_approved" in receipt)):
        raise BundleError("receipt release flags differ")
    files = _archive_files(archive)
    expected_names = set(spec.source_names) | {README_NAME, MANIFEST_NAME}
    if set(files) != expected_names:
        raise BundleError("archive member scope differs from allowlist")
    try:
        manifest = json.loads(files[MANIFEST_NAME])
    except json.JSONDecodeError as exc:
        raise BundleError("source hash manifest is invalid") from exc
    if (manifest.get("version") != spec.version or manifest.get("status") != "REVIEW_ONLY"
            or manifest.get("journal_submission_approved") is not False
            or manifest.get("original_raw_data_included") is not False
            or manifest.get("original_byte_replay_verified") is not False
            or manifest.get("source_git_revision_bound") is not False):
        raise BundleError("review-only provenance flags differ")
    if (any(manifest.get(key) != value for key, value in _release_flags(spec).items())
            or (spec in (V10_SPEC, V11_SPEC, V12_SPEC, V13_SPEC, V14_SPEC, V15_SPEC) and "public_release_approved" in manifest)):
        raise BundleError("manifest release flags differ")
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != len(spec.source_names):
        raise BundleError("manifest source file count differs")
    by_name = {row.get("path"): row for row in rows if isinstance(row, dict)}
    if set(by_name) != set(spec.source_names):
        raise BundleError("manifest source scope differs")
    for name in spec.source_names:
        data = files[name]
        row = by_name[name]
        if row.get("sha256") != _sha(data) or row.get("bytes") != len(data):
            raise BundleError(f"manifest hash or size differs: {name}")
        _screen(name, data)
        if compare_sources:
            path = ROOT / name
            if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
                raise BundleError(f"current local source differs: {name}")
    _check_decision_bindings({name: files[name] for name in spec.source_names}, spec)
    readme = manifest.get("readme")
    if not isinstance(readme, dict) or readme.get("path") != README_NAME or files[README_NAME] != spec.readme.encode("utf-8"):
        raise BundleError("review-only README differs")
    if readme.get("sha256") != _sha(files[README_NAME]) or readme.get("bytes") != len(files[README_NAME]):
        raise BundleError("README hash or size differs")
    _screen(README_NAME, files[README_NAME])
    if receipt.get("manifest_sha256") != _sha(files[MANIFEST_NAME]):
        raise BundleError("manifest differs from receipt")
    if receipt.get("source_file_count") != len(spec.source_names) or receipt.get("archive_members") != len(files):
        raise BundleError("receipt source count differs")
    return {"version": spec.version, "status": "REVIEW_ONLY", "archive_sha256": digest,
            "manifest_sha256": _sha(files[MANIFEST_NAME]),
            "source_file_count": len(spec.source_names), "archive_members": len(files),
            "local_sources_match": True if compare_sources else None}


def build(*, output: Path = OUTPUT, spec: BundleSpec = V11_SPEC) -> dict[str, Any]:
    output = Path(output)
    receipt_path = _receipt_path(output)
    if output.exists() or receipt_path.exists():
        raise FileExistsError("review bundle or receipt already exists")
    source = _source_bytes(spec)
    readme = spec.readme.encode("utf-8")
    manifest_bytes = _json_bytes(_manifest(source, readme, spec))
    files = dict(source)
    files[README_NAME] = readme
    files[MANIFEST_NAME] = manifest_bytes
    for name, data in files.items():
        _screen(name, data)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as raw:
            os.chmod(output, 0o600)
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    for name, data in sorted(files.items()):
                        _add(archive, name, data)
        receipt = {
            "version": spec.version, "status": "REVIEW_ONLY",
            **_release_flags(spec), "journal_submission_approved": False,
            "archive_sha256": _sha(output.read_bytes()),
            "manifest_sha256": _sha(manifest_bytes),
            "source_file_count": len(spec.source_names), "archive_members": len(files),
            "archive_bytes": output.stat().st_size,
        }
        with receipt_path.open("x", encoding="utf-8") as stream:
            os.chmod(receipt_path, 0o600)
            stream.write(_json_bytes(receipt).decode("utf-8"))
        # Detect source edits during packaging. Later edits are caught by verify.
        verify(archive=output, compare_sources=True)
    except Exception:
        output.unlink(missing_ok=True)
        receipt_path.unlink(missing_ok=True)
        raise
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--bundle-version", choices=tuple(BUILD_TARGETS), default="v11",
                        help="select the default archive and, for build, source specification")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--no-local-compare", action="store_true",
                        help="verify archived hashes without comparing current workspace files")
    args = parser.parse_args()
    default_archive, spec = BUILD_TARGETS[args.bundle_version]
    archive = args.archive or default_archive
    result = (build(output=archive, spec=spec) if args.action == "build" else
              verify(archive=archive, compare_sources=not args.no_local_compare))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
