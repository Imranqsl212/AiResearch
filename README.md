# When the Tests Pass but the Benchmark Says No

## Prospective research status (5 October 2026)

The current [8 October next actions](docs/NEXT_READY_ACTIONS_20261008.md) separate the author-review submission path from the proposed confirmatory study.

The completed 40-episode study below is an **exploratory benchmark audit**. A new, separately versioned study is under development; **no prospective v1 main episodes have been collected**. The [5 October readiness update](docs/READINESS_UPDATE_20261005.md), [12-gate evidence matrix](docs/MAIN_RELEASE_GATE_MATRIX_20261005.md), and [Russian handoff](docs/READY_HANDOFF_RU_20261005.md) are the current decision records. The [research audit](research_audit.md) identifies why the old unavailable-task labels and finite tests cannot establish true impossibility or security. The [experiment design](experiment_design.md) defines repairable, proved unrepairable, and evaluator-mismatch states, with controlled feedback and retrieval arms. The [root experiment manifest](experiment_manifest.json) remains `NOT_READY` and its main-run preflight fails closed. The [reproduction guide](reproduction/README.md) distinguishes the old local analysis from v1 engineering checks; [older gate matrix](docs/V1_GATE_MATRIX.md) and [4 October readiness audit](docs/READINESS_BLOCKERS_20261004.md) retain the earlier evidence record.

The original four controlled finite fixtures cover [authorization](benchmark_spec.md), [path boundaries](docs/FINITE_PATH_V2.md), [transaction replay](docs/FINITE_REPLAY_V3.md), and [counter races](docs/FINITE_RACE_V4.md). Three additional authored batches bring the catalog to 20 mechanisms and 100 C1–C5 rows. The [machine admission pre-review](analysis/admission_review_20261004.json) records human review as missing; a later [semantic audit](docs/BATCH_C_SEMANTIC_ADMISSION_BLOCKER_20261005.md) found that batch C's C3/C4 impossibility witnesses currently depend on a task-level observation flag, so its structural pass does not admit those families. A [separate v7 candidate](docs/BATCH_C_V7_SEMANTIC_CANDIDATE_20261005.md) replaces that gate with explicit conflicting worlds but remains unreviewed. A [100-slot excluded rehearsal](docs/FULL_CATALOG_REHEARSAL_20261005.md) verified the registered finite catalog's collection path without model calls. A separate [40-slot live feasibility block](docs/FULL_CATALOG_LIVE_FEASIBILITY_20261005.md) produced 30 valid excluded episodes and 14 agent-generated secure onsets across 10 families, with 10 invalidations. [All 14 matched C5 continuations](docs/C5_ALL_ONSETS_EXCLUDED_AUDIT_20261005.md) later completed without branch invalidations. A distinct [40-slot C2 R0/R1 live pilot](docs/R1_TWENTY_LIVE_FEASIBILITY_20261005.md) used the unreviewed 20-family R1 v0.1 candidate and yielded 38 valid excluded episodes, two retained invalidations, and 19 complete family pairs. A [separate R1 v0.2 candidate](docs/R1_TWENTY_CANDIDATE_V2_20261005.md) repairs seven source paragraphs but has no model runs. These are bounded calibration and engineering results, not prospective main evidence or a retrieval-effect estimate. The [SQLite injection calibration](benchmark/real_code_sqli_notes.md) and command-injection calibration add two isolated real-code fixtures with host-owned checks; neither includes an agent-written repair.

The [excluded v7 live pilot](docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md) completed 30/30 slots in two authored families at temperature 0.3, with three seeds per family-condition cell. C3 and C4 showed no difference in early voluntary stopping or submitted-candidate counts across six matched blocks. One selected secure onset yielded a descriptive C5 continuation: truthful PASS stopped after one decision, false FAIL used all three. Neither result estimates a population effect.

Separate `qwen3:4b` and `gemma3:4b` RAG blocks each validated nine excluded C1/C2/C4 × R0/R1/R2 slots. The [cross-model descriptive audit](docs/CROSS_MODEL_RAG_EXCLUDED_RESULT_20261004.md) verifies matched initial requests apart from the model field, but four of 13 source files differ between runs. Qwen's source archive was recovered after collection; Gemma's was archived before collection. Gemma stopped on its first action in all C1/C4 cells, without evidence that it understood the C4 impossibility proof. Input lengths differ between retrieval arms, and one seed per cell cannot establish a RAG effect or model difference. The [official Docker safety receipt](sandbox/safety_checks/latest_result.json) passed 11/11 checks on 4 October for its recorded image, policy, and daemon; a prospective main freeze must bind its own exact runtime. The repository now contains 20 authored finite families with a machine admission pre-review and two isolated real-code calibrations. Main collection still requires human admission review of all 20, broader real-code security tasks, repeated context-controlled and cross-model observations, blind annotation, a clean freeze, and a full main release gate. The existing paper remains the report of the exploratory cohort; its empirical percentages must not be read as prospective v1 results.

An exploratory research project on what a local coding agent does after security feedback rejects its cryptographic or web code. The completed study used an Ollama `qwen3:4b` agent, synthetic local Python tasks, bounded tools, and a Docker candidate runtime.

**Current manuscript:** [full paper (Markdown)](paper/final.md), identified [PDF](paper/submission/full_paper.pdf) and [Word](paper/submission/full_paper.docx), and anonymous peer-review [PDF](paper/submission/full_paper_anonymous.pdf) and [Word](paper/submission/full_paper_anonymous.docx). The identified PDF has 16 A4 pages and the anonymous PDF has 15, at 12 pt and single spacing. The 237-word abstract, six generated figures, four tables, limitations, 25 linked primary sources, and reproduction instructions are in the paper. A [local v6 author-review bundle](paper/AUTHOR_REVIEW_BUNDLE_20261005.md) binds the current drafts, separate pilot audits, independent terminal-receipt recount, and original-archive byte audit; it remains `REVIEW_ONLY`. [Funding and conflict declarations](paper/AUTHOR_SUBMISSION_DECISIONS_20261005.md), venue, data access, privacy review, and author scientific approval remain open. See the [submission handoff](paper/SUBMISSION_HANDOFF_20261005.md) and [journal shortlist](paper/VENUE_SHORTLIST_20261005.md).

## What was actually collected

The executable catalog contains 80 task definitions (20 families × four condition cards). The resource bounded overnight study used **five** main families with four condition cards and guidance on/off: **40 episodes**, one per arm. A separate AEAD pilot used **eight** episodes. The remaining catalog definitions were validated as fixtures but were not part of this main empirical cohort. Older smokes and a separate containment *simulation* are retained as engineering records; they are not pooled with this study.

The final code passed the benchmark's limited checks in 16/20 nominally repairable main episodes. In 9/20 nominally unavailable episodes the same family checks passed, but a hidden acceptance rule rejected the result. Thus this dataset cannot establish that the agent recognized genuinely impossible tasks. Only five families and one run per arm were collected; the planned confirmatory GEE analysis was not run. See [paper/final.md](paper/final.md) for definitions, denominators, and caveats.

A [post hoc source-fidelity audit](docs/EXPLORATORY_SOURCE_FIDELITY_20261005.md) found that 63/77 logged Python submissions parse as written. Eleven more contain unquoted `<REDACTED>` markers inserted by the historical logger, and three have other syntax errors. The expressions erased by redaction are not recoverable from the saved logs, so exact AST comparisons for all 77 submissions cannot be made. Future excluded finite runs now [retain a full evaluator receipt at each completed check](docs/PER_ACTION_CHECK_LOGGING_20261005.md), with an explicit status when no valid receipt exists; this changes neither the historical data nor main eligibility.

**The memorable finding:** a hidden veto can make an agent's continued attempts look like stubbornness, while the benchmark itself withholds the reason that no code change will be accepted. The paper measures this evaluation conflict directly and makes its limits explicit.

## Reproduce the reported numbers

The analysis reads saved local logs and receipts without executing model generated code:

```sh
python3 -B -m analysis.paper_pipeline --output paper/artifacts
```

This creates [results.json](paper/artifacts/results.json), [per-run metrics](paper/artifacts/run_metrics.csv), condition and family tables, a [historical cohort inventory](paper/artifacts/historical_inventory.csv), and an [input hash ledger](paper/artifacts/input_hashes.csv). The pipeline validates the main and pilot manifests, source archive checksums, and per-run receipts. Original inputs in `experiments/runs/` and `experiments/raw_archive/` remain untouched. Those raw directories are excluded from Git pending a privacy and code release review; a clone without them cannot reproduce the counts from raw data. The derived tables in this workspace support inspection but are not a substitute for the original traces.

Build both PDF/Word versions and six figures after running the analysis:

```sh
sh reproduction/render_paper.sh
```

The script uses the bundled local Python when present, or a Python with Pillow, ReportLab, python-docx, and pypdf installed as listed in [render requirements](paper/requirements-render.txt). Set `PAPER_PYTHON` to choose another interpreter. No Docker or Ollama call occurs during analysis or paper rendering. The frozen experiment source commit was `98a4dcf414672c1725e4acdb9f08045370aa7f64`; `analysis/paper_pipeline.py` is post collection analysis code. Detailed steps and checks are in [paper/README.md](paper/README.md).

## Для соавтора и ментора

Мы исследуем, что делает локальный AI агент после сообщения об ошибке безопасности: исправляет ли программу, подбирает похожие варианты или прекращает попытки. Для каждой задачи у него есть небольшой фрагмент криптографического или веб кода, ограниченные инструменты и проверка в изолированном контейнере. Часть задач даёт подробную обратную связь, часть — короткую; в половине запусков агент получает заранее подготовленную справку по теме.

Ночной запуск уже завершён: 8 отдельных пилотных и 40 основных эпизодов. Статья показывает конкретные действия агента и ограничения нашего checker’а. Самое существенное: метка «нерешаемая задача» сейчас реализована скрытым отказом принять ответ, даже если внутренние тесты пройдены. Поэтому мы честно не утверждаем, что доказали способность агента понять, когда нужно остановиться. Это полноценный отчёт о состоявшемся исследовании и одновременно основание для улучшения следующего эксперимента.

Начните с [PDF статьи](paper/submission/full_paper.pdf). Для простого русского объяснения исходного замысла есть [исследовательский гид](docs/RESEARCH_GUIDE_RU.md); его старые оперативные статусы могут не соответствовать нынешним результатам. Источники и текущие выводы проверяйте по новой статье.

## Repository map

| Path | Purpose |
| --- | --- |
| `benchmark/`, `crypto_target/`, `web_target/` | Local task definitions, templates, retrieval corpus, reference implementations, and finite tests. |
| `agent/` | Provider neutral contract and local Ollama adapter. |
| `sandbox/` | Docker candidate runtime, policy, image reference, and safety checks. |
| `experiments/` | Local manifests, schedules, append only ledgers, logs, receipts, and archives. Most raw outputs are Git ignored. |
| `analysis/paper_pipeline.py` | Read only reconstruction of reported empirical numbers and data integrity checks. |
| `paper/` | Manuscript, generated figures, derived data, PDF and DOCX, prior protocol manuscript archive. |
| `literature/`, `docs/` | Earlier literature review, protocol, design notes, and historical audit. |

The exact Docker safety receipt and benchmark validity limitations are described in the paper. Do not use the exploratory percentages as population estimates or a general claim of code security.
