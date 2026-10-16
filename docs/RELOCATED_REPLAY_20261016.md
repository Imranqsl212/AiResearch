# Relocated reproduction check — 16 October 2026

## Historical paper counts

The public data revision
[`37074c198237ade67eb76921333b2835d329c863`](https://github.com/Imranqsl212/AiResearch/tree/37074c198237ade67eb76921333b2835d329c863)
was extracted to a different directory for a local replay. Its historical
result-index entries contain absolute paths to the original author's checkout.
The earlier `analysis.paper_pipeline.local_path` used such a path whenever it
still existed on the machine. In the relocated directory the command failed
when it tried to make that outside path relative to the new repository root.

`analysis/paper_pipeline.py` now resolves each recorded artifact to the
matching path **inside the active checkout**, requires the file to exist there,
and rejects traversal or a symlink outside that checkout. This changes file
selection only; original manifests, logs, receipts, and archives remain
unchanged. A focused regression test keeps the old absolute path present while
verifying that the new checkout's bytes are selected.

With that one analysis-file fix applied to the relocated data revision,
`python3 -B -m analysis.paper_pipeline --output paper/artifacts` completed
without the model or Docker. It independently returned 40 main episodes,
16 accepted repairable final candidates, **9/20** raw-test-pass/hidden-veto
disagreements in the nominally unavailable arm, 77 submissions, 14 unparseable
logged sources, and 0/81 per-action raw evaluator receipts. The eight derived
result and inventory files written by the pipeline matched the current
workspace byte for byte. Its ninth output, `input_hashes.csv`, differed in
two source-version rows (`analysis/paper_pipeline.py` and
`docs/OVERNIGHT_PROFILE.md`), as expected when comparing the 12 October data
revision to the later analysis/workspace version. The current input ledger
also differs from the archived original-package inventory in a third row,
`experiments/executable_episode.py`; see the
[original-byte audit](../paper/ORIGINAL_ARCHIVE_PROVENANCE_AUDIT_20261008.md).

This is a relocated **saved-data replay**, not a new agent experiment or an
independent rerun of the original evaluator. It confirms the reported counts
from tracked records under the stated code revision; it does not establish
privacy clearance or an external chain of custody.

## Separately excluded pilot and continuation archives

The same relocation check exposed old absolute paths in the v7 excluded-pilot
and C5 continuation auditors. Their readers now map recorded paths into the
declared checkout and fail when a local input is absent, modified, or outside
that checkout. For v7, the auditor also checks that Python imported the
registry and evaluator modules from the same checkout whose archived source
hashes it verifies. An in-process mixed-checkout replay is rejected.

With patched audit code in a separate extracted Git archive, the v7 pilot
audit rechecked **30/30** saved slots, and its selected C5 fork matched the
saved report. The separate 14-pair C5 audit rechecked **14/14** saved pairs; its
complete JSON report had the same SHA-256 in the original and relocated
directories. Removing a local archived request caused the relocated audit to
fail even while the original recorded path was still available. These are
saved-data checks, not fresh model calls. A Git archive contains no `.git`, so
the episode-level `git_commit_verified` field is false there; a local Git
clone is needed for the commit-object check.

After committing the fixes at `a0e159f7`, a separate **local Git clone** of
that branch reproduced the main summary (40 episodes, 16 accepted repairable
final candidates, 9/20 hidden-veto discordance) and left the clone clean after
regenerating `paper/artifacts`. All 30 v7 pilot manifests in that clone passed
proof and candidate replay; all 30 had `git_commit_verified=True`. Both v7
audits passed, and the 14-pair C5 report was byte-identical to the native
report. The loader's general `eligible` flag indicates a valid episode record;
the v7 manifests explicitly set `eligible_for_main_analysis=False`, so these
30 excluded pilot episodes are **not** part of a prospective main analysis.
The clone came from the local repository; a separate remote checkout remains
an external reproduction step.
