# Manuscript reproduction and handoff

The manuscript in [final.md](final.md) is a full exploratory study report. The [PDF](submission/full_paper.pdf) is the review copy; the [Word file](submission/full_paper.docx) is editable. Six generated PNG figures are in `figures/`. The pre empirical protocol manuscript is preserved in `archive/protocol_before_empirical_revision.md`.

## Required local inputs

The raw main and pilot episodes are located under `../experiments/runs/`, with result indexes, manifests, schedules, ledgers, nightly gate report, and sealed archive records under `../experiments/`. These directories are deliberately Git ignored pending release review. A clean clone without this separately retained raw archive **cannot** reproduce all numbers from source trajectories. The local derived tables in `artifacts/` are useful for audit but do not substitute for those raw files.

The main experiment identifier is `rag-overnight-v2-main-0-5-0`; the separate pilot identifier is `rag-overnight-v2-pilot-0-5-0`. The study manifest cites Git commit `98a4dcf414672c1725e4acdb9f08045370aa7f64`. The analysis and manuscript were written after collection; their Git state should be recorded at submission. A current source checkout alone may differ from frozen adapter code, so use the study commit to inspect the executed implementation.

## Recompute

From the repository root:

```sh
python3 -B -m analysis.paper_pipeline --output paper/artifacts
python3 -B -m analysis.auxiliary_sidecar_audit
python3 -B -m unittest tests.test_paper_pipeline
```

The analysis uses the Python standard library. It validates every main and pilot artifact, reads but never executes submitted source, hashes every input before and after analysis, and writes only into `paper/artifacts/`. `results.json` contains group summaries and exploratory family contrasts. `run_metrics.csv` traces every included run back to its log and receipt path. `input_hashes.csv` inventories inputs. `historical_inventory.csv` makes exclusions explicit. The script does **not** run the model, Docker, or security experiments.

The separate auxiliary audit searches local, unsealed Docker sidecar logs by candidate-source hash. Its result is in `artifacts/auxiliary_sidecar_audit.json`. These logs are not uniquely tied to an action and are not used for any paper outcome or stopping metric. A clone without `sandbox/logs/` cannot reproduce this auxiliary check.

The PDF and Word builder requires Pillow, ReportLab, python-docx, and pypdf. The installed workspace runtime on this Mac has Pillow, ReportLab 4.4.9, python-docx 1.2.0, and pypdf 6.10.0:

```sh
/Users/imranmzakirov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m paper.build_submission
```

On another machine, invoke `python3 -B -m paper.build_submission` from an environment with those dependencies and an available Arial compatible TrueType font. The current chart builder references macOS Arial in `/System/Library/Fonts/Supplemental/`; a portable version should configure a freely distributable font before independent rendering. It verifies key numerical anchors before typesetting and extracts text from the generated PDF to check required sections.

## Claims and limitations to retain when sharing

- `16/20` is acceptance by **finite local checks** on nominally repairable final candidates, not a proof of secure code.
- `9/20` policy rejected episodes pass the raw family tests and fail a hidden condition rule. They do not test whether the agent recognizes a genuinely impossible programming requirement.
- `0/81` per-action check records preserve the raw family test result. The terminal disagreement cannot be assigned to an earlier action in the trajectory; extra revisions must not be described as occurring after a known raw pass.
- `0/15` recovered explicit success statements contradict the limited benchmark receipt. Five main final claims were not recovered; the historical raw parser labeled all 40 unknown.
- The five main families have one run per arm. Family resampling is descriptive; the planned GEE and independently coded strategy transition outcome are unavailable.
- Eleven of 14 unparseable logged source strings contain redaction markers; the remaining three have no identified cause. Source comparisons use only the parseable subset and are not semantic strategy labels.

Source links are in the numbered references of the article; an editable BibTeX companion is [references.bib](references.bib). The publication review and unresolved validity findings are documented in [PAPER_SUBMISSION_AUDIT.md](../docs/PAPER_SUBMISSION_AUDIT.md).
