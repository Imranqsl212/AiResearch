# C5 paper and release candidates

The [manuscript](manuscript.md) is the primary C5 research draft. Read the [identified PDF](checker_feedback.pdf) or [anonymous PDF](checker_feedback_anonymous.pdf). The earlier stopping-attribution manuscript has a distinct research question and remains reproducible at its original paths.

## Rebuild

The following commands run from the repository root. The PDF builder uses ReportLab, pypdf, Pillow and python-docx from the existing manuscript runtime. Change the Python path to use a matching local environment.

```sh
paper_python="${PAPER_PYTHON:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
"$paper_python" -B -m paper.c5.render
"$paper_python" -B -m paper.c5.release --output .local_private/c5-release-20261123
python3 -B -m analysis.c5_public_trajectories
python3 -B data/c5/check_release.py
```

The identified data ZIP contains the JSONL, schema, provenance, external observation controls, dataset card, citation file, standalone checker and checksums. The anonymous ZIP contains its own README, a standalone checker, the anonymous PDF, bounded event fields and digests. A closed allowlist omits private decision forms, earlier author-review archives, raw model text and Git history. The PDF and archive text are screened for direct identities and host-specific markers. Previously published counts and searchable paper text can still identify the research. The local anonymous copy supports review; distribution depends on the venue’s policy. The repository itself is publicly identified.

To create a local anonymous Git mirror, pass `--mirror /path/to/new-review-repository` to the same release command. It creates a single anonymous commit from the verified archive and configures no remote. Use a fresh directory.

The local OSF preparation command below exports the protocol, four candidate schedules, analysis files and immutable-response hash lines. Compare the output with the [draft receipt](../../docs/c5_registration_draft_receipt.json). Registration requires author approval and a registry timestamp before eligible collection.

```sh
python3 -B -m paper.c5.prepare_registration --roster broad19 --output .local_private/c5-release-20261123/registration-draft.zip
```

[Individual task histories and field definitions](../../data/c5/README.md) · [Archival analysis, statistical design and power](../../docs/C5_PROSPECTIVE_STATISTICAL_PLAN_20261123.md) · [Scope and publication decisions](../../docs/C5_STUDY_STATUS.md)
