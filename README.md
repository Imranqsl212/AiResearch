# When the Tests Pass but the Benchmark Says No

## Prospective research status (4 October 2026)

The completed 40-episode study below is an **exploratory benchmark audit**. A new, separately versioned study is under development; **no prospective v1 main episodes or publication-grade agent results have been collected**. The [research audit](research_audit.md) identifies why the old unavailable-task labels and finite tests cannot establish true impossibility or security. The [experiment design](experiment_design.md) defines repairable, proved unrepairable, and evaluator-mismatch states, with controlled feedback and retrieval arms. The [root experiment manifest](experiment_manifest.json) remains `NOT_READY` and its main-run preflight fails closed. The [reproduction guide](reproduction/README.md) distinguishes the old local analysis from v1 engineering checks; [current status](FINAL_RESEARCH_STATUS.md), [gate matrix](docs/V1_GATE_MATRIX.md), and [readiness audit](docs/READINESS_BLOCKERS_20261004.md) list the remaining evidence gaps.

Four controlled finite fixtures now cover [authorization](benchmark_spec.md), [path boundaries](docs/FINITE_PATH_V2.md), [transaction replay](docs/FINITE_REPLAY_V3.md), and [counter races](docs/FINITE_RACE_V4.md). Their 20 proofs and 1,430 candidate/condition decisions pass [exhaustive calibration](docs/FINITE_FIXTURE_CALIBRATION_20261004.md) against separate reference checkers. All four have excluded live collector pilots. The [counter-race C5 pilot](docs/COUNTER_RACE_V4_LIVE_PILOT_20261004.md) captured three oracle-secure submissions rejected by a deliberately mismatched gate in one episode; the [replay prompt follow-on](docs/V3_JSON_PROTOCOL_V2_RESULT_20261004.md) validated all five fresh slots after five earlier protocol invalidations. A [SQLite injection calibration](benchmark/real_code_sqli_notes.md) adds one isolated real-code fixture with a host oracle: its strong suite caught two planned insecure mutations that its weak suite missed. These are bounded calibration and pilot results, not a prospective security-code benchmark.

Separate `qwen3:4b` and `gemma3:4b` RAG blocks each validated nine excluded C1/C2/C4 × R0/R1/R2 slots. The [cross-model descriptive audit](docs/CROSS_MODEL_RAG_EXCLUDED_RESULT_20261004.md) verifies matched initial requests apart from the model field, but four of 13 source files differ between runs. Qwen's source archive was recovered after collection; Gemma's was archived before collection. Gemma stopped on its first action in all C1/C4 cells, without evidence that it understood the C4 impossibility proof. Input lengths differ between retrieval arms, and one seed per cell cannot establish a RAG effect or model difference. The [official Docker safety suite](sandbox/safety_checks/latest_result.json) passed 11/11 checks for the current exact runtime. Main collection still requires at least 20 independently reviewed matched families, broader real-code security tasks, repeated context-controlled and cross-model observations, blind annotation, a clean freeze, and a full main release gate. The existing paper remains the report of the exploratory cohort; its empirical percentages must not be read as prospective v1 results.

An exploratory research project on what a local coding agent does after security feedback rejects its cryptographic or web code. The completed study used an Ollama `qwen3:4b` agent, synthetic local Python tasks, bounded tools, and a Docker candidate runtime.

**Current manuscript:** [full paper (Markdown)](paper/final.md), [PDF](paper/submission/full_paper.pdf), [editable Word file](paper/submission/full_paper.docx). The paper contains six generated figures, three tables, limitations, 22 linked primary sources, and reproduction instructions.

## What was actually collected

The executable catalog contains 80 task definitions (20 families × four condition cards). The resource bounded overnight study used **five** main families with four condition cards and guidance on/off: **40 episodes**, one per arm. A separate AEAD pilot used **eight** episodes. The remaining catalog definitions were validated as fixtures but were not part of this main empirical cohort. Older smokes and a separate containment *simulation* are retained as engineering records; they are not pooled with this study.

The final code passed the benchmark's limited checks in 16/20 nominally repairable main episodes. In 9/20 nominally unavailable episodes the same family checks passed, but a hidden acceptance rule rejected the result. Thus this dataset cannot establish that the agent recognized genuinely impossible tasks. Only five families and one run per arm were collected; the planned confirmatory GEE analysis was not run. See [paper/final.md](paper/final.md) for definitions, denominators, and caveats.

**The memorable finding:** a hidden veto can make an agent's continued attempts look like stubbornness, while the benchmark itself withholds the reason that no code change will be accepted. The paper measures this evaluation conflict directly and makes its limits explicit.

## Reproduce the reported numbers

The analysis reads saved local logs and receipts without executing model generated code:

```sh
python3 -B -m analysis.paper_pipeline --output paper/artifacts
```

This creates [results.json](paper/artifacts/results.json), [per-run metrics](paper/artifacts/run_metrics.csv), condition and family tables, a [historical cohort inventory](paper/artifacts/historical_inventory.csv), and an [input hash ledger](paper/artifacts/input_hashes.csv). The pipeline validates the main and pilot manifests, source archive checksums, and per-run receipts. Original inputs in `experiments/runs/` and `experiments/raw_archive/` remain untouched. Those raw directories are excluded from Git pending a privacy and code release review; a clone without them cannot reproduce the counts from raw data. The derived tables in this workspace support inspection but are not a substitute for the original traces.

Build the PDF, Word file, and six figures after running the analysis:

```sh
/Users/imranmzakirov/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m paper.build_submission
```

This machine specific command uses the bundled Python environment with Pillow, ReportLab, python-docx, and pypdf. On another computer, use Python with those four libraries installed; no Docker or Ollama call occurs during analysis or paper rendering. The frozen experiment source commit was `98a4dcf414672c1725e4acdb9f08045370aa7f64`; `analysis/paper_pipeline.py` is post collection analysis code. Detailed steps and checks are in [paper/README.md](paper/README.md).

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
