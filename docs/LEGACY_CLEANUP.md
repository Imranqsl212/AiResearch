# Recoverable cleanup of the former AVB-Bench workspace

On 2026-09-29, at the user's direction, legacy **AVB-Bench / Beyond Automated Scanning** materials were moved out of this repository into the macOS Trash folder:

`/Users/imranmzakirov/.Trash/when-to-stop-legacy-avb-2026-09-29/`

This was a move, not permanent deletion. No file was overwritten. The archive retains 47 top-level entries plus `docs/` (8 files), `figures/` (10 files), and `tests/` (1 file): 66 direct archived entries in total. Some top-level entries are directories containing additional files. Emptying the macOS Trash would make recovery harder; restore from this folder if any item is needed later.

## What was moved

- The old mixed `README.md` was preserved as `README-legacy.md` before the repository README was rewritten for the current study.
- Former AVB manuscript and submission materials: `QUICK_READ.md`, `full_paper_draft.md`, `journal_submission.*`, `submission/`, `submission_audit.md`, `symposium_presentation.*`, `poster/`, `proposal_draft.md`, `paper_outline.md`, `editorial_packet.md`, `reviewer_response.md`, `venue_requirements.md`, and the old manuscript/render scripts.
- Former AVB research planning, citations, templates, and generated support: `agent_conditioned_blindness.md`, `ambition_extension_review.md`, `communication_package.md`, `course_material_analysis.md`, `data_collection_template.csv`, `discovery_expansion_plan.md`, `experiment_protocol.md`, `hackerone_report_audit_template.csv`, `human_session_template.csv`, `literature_matrix.csv`, `novelty_positioning.md`, `public_case_evidence.csv`, `real_world_case_template.csv`, `references.bib`, `related_work_updates.md`, `research_journal.md`, `sample_manifest_template.csv`, `sources.md`, `configs/`, `data/`, `hashes/`, `logs/`, `pipeline/`, `schemas/`, `figures_src/`, and `reproduce.sh`.
- Eight explicitly AVB-titled documents under archived `docs/`: `AVB_V2_ARCHITECTURE.md`, `AVB_V2_EVALUATION_PROTOCOL.md`, `BENCHMARK_AUDIT.md`, `CLAIMS.md`, `ERROR_TAXONOMY.md`, `FINAL_RESEARCH_AUDIT.md`, `LITERATURE_REVIEW_V2.md`, and `RATE_LIMITING.md`.
- Ten top-level legacy PNGs under archived `figures/`; the current `figures/stopping_experiment/` remains in the repository.
- The former AVB-v2 test `tests/test_v2_pipeline.py`; the current When-to-Stop test suite remains.

The current `agent/`, `analysis/`, `benchmark/`, `docs/`, `experiments/`, `literature/`, `paper/`, `sandbox/`, `tables/`, and relevant `figures/` files were retained. The cleanup changes project scope, not the preregistered hypotheses. Raw experiment data were not discarded; the only current stored trajectory is the scripted fixture.
