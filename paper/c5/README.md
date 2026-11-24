# What Is One More Step Worth After a False Alarm?

The [manuscript](manuscript.md) is the primary C5 research draft. Read the [identified PDF](checker_feedback.pdf) or [anonymous PDF](checker_feedback_anonymous.pdf). Its historical graph shows failing-candidate counts of **4/1, 8/6 and 5/7** after decisions one, two and three (truthful PASS / false FAIL; 14 branches per arm). All historical branches knew a three-decision limit; the graph does not identify the effect of announcing a shorter budget. See the [prefix audit](../../analysis/c5_budget_prefix_audit_20261124/audit.json).

The [new factorial protocol](../../docs/C5_BUDGET_STATISTICAL_PROTOCOL_20261124.md) and [runner](../../experiments/c5_budget_README.md) generate four fresh continuations from a common verified repair. The announced and enforced horizon changes together. The [synthetic runner receipt](../../experiments/c5_budget_calibration_receipt.json), [matched correct/defective challenge](../../docs/C5_EVIDENCE_CHALLENGE.md) and [four upstream test-correction cases](../../external_checker_audit_20261124/README.md) have separate provenance and limitations. Scripted policies are not model findings; external cases still need independent admission and agent outcomes.

The prospective analysis weights families equally, retains missingness bounds and corrects four model-specific tests. The proposed nineteen-family design is not generally powered for small interactions. No confirmatory episodes have been collected. The [separate CLI pilot](../../docs/C5_CLI_PILOT_20261124.md) collected 16 of 40 planned episodes across two configurations on one benign numerical task. The [public decision table](../../analysis/c5_cli_pilot_20261124.json) records the outcome and action sequence for each scheduled episode. The earlier stopping-attribution manuscript and [November 23 stopping-focused plan](../../docs/C5_PROSPECTIVE_STATISTICAL_PLAN_20261123.md) retain their original paths and questions.

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

The new local OSF preparation command exports the verdict × budget protocol, four candidate schedules, source bindings, analysis files and immutable-response hash lines. Compare its output with the [budget packet receipt](../../docs/c5_budget_registration_receipt_20261124.json). It makes no model calls and does not register the study. Independent admission, author approval and a verifiable registry timestamp must precede eligible collection.

```sh
python3 -B -m paper.c5.prepare_budget_registration --output .local_private/c5-release-20261124/budget-registration-draft.zip
```

The earlier stopping-focused packet and its [original draft receipt](../../docs/c5_registration_draft_receipt.json) remain reproducible with the unchanged builder:

```sh
python3 -B -m paper.c5.prepare_registration --roster broad19 --output .local_private/c5-release-20261123/registration-draft.zip
```

[Individual task histories and field definitions](../../data/c5/README.md) · [New factorial design and power](../../docs/C5_BUDGET_STATISTICAL_PROTOCOL_20261124.md) · [Earlier statistical plan](../../docs/C5_PROSPECTIVE_STATISTICAL_PLAN_20261123.md) · [Scope and publication decisions](../../docs/C5_STUDY_STATUS.md)
