# Data availability for the exploratory manuscript — updated 12 October 2026

These are **author-review notes**, not text approved for a journal submission.
The current research branch tracks the historical raw trajectories, original
archive, sanitized candidate, corrected-oracle pilot runs, code, and derived
tables. Some filenames retain `PRIVATE` or `REVIEW_ONLY` from an earlier release
workflow, but those labels do not make a committed file private. The author has
chosen to publish the experimental artifacts on GitHub as they are. Availability
to an external reader depends on pushing the branch and identifying the exact
public revision; the default branch can lag. No data DOI or journal-specific
supplementary package has been established.

## Draft statement after the exact public revision is verified

> Analysis code, derived tables, and the archived trajectories used for the
> historical and pilot counts are available in the project's public GitHub
> repository at [exact revision and URL to be inserted after publication].
> The repository contains unredacted local path metadata and model-generated
> outputs. The counts can be checked with the documented analysis commands,
> subject to the recorded software and provenance limitations. No archival DOI
> or independent rerun is claimed.

Before using that statement, verify the public revision contains every cited
input, run the checks from a fresh checkout, identify the journal's data and
anonymity requirements, and obtain author sign-off on the exact wording.

## If the journal requires a separate supplementary deposit

A separate reviewed deposit may use the original bytes or a transformed
candidate. The existing sanitized candidate recomputes path-independent
tables, but transformation changes source hashes and does not replay the
original hash chain. Its residual privacy/content review is incomplete. State
the precise relation between any deposited copy and the original archives;
do not describe a transformed deposit as original-byte reproduction. Record
the repository revision, persistent identifier, and reviewer access route
only after they exist.

The [submission handoff](SUBMISSION_HANDOFF_20261005.md) tracks author,
declaration, venue, and final package decisions. GitHub publication does not
itself mean the manuscript is ready for journal submission.
