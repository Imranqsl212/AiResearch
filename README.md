# The Tests Passed. The Benchmark Said No

This repository studies what a local coding agent does after a security checker rejects its Python code. It contains a completed **exploratory benchmark audit**, separate feasibility pilots, and an unfinished prospective study. These cohorts have different protocols and are never pooled.

## Current result

The historical study used `qwen3:4b` on five selected task families: **40 main episodes**, one run per condition and guidance arm. A separate AEAD pilot has eight episodes. In **9 of 20** final candidates labeled nominally unavailable, the implemented family tests passed but a hidden acceptance rule rejected the result. This is a measurement defect in that evaluator; it does not prove that those tasks were truly impossible or that the submitted code was secure. The agent's response to truthful impossibility feedback was not measured in this historical cohort.

![Raw finite tests versus final benchmark acceptance in the historical runs](paper/milestone/hidden_veto_results.png)

A later [corrected-oracle v7 pilot](docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md) completed 30 excluded episodes in two authored finite families with three seeds per cell. Its C3/C4 matched blocks showed no reduction in submitted candidates or early stopping under truthful contradiction feedback. One selected secure-candidate continuation differed under truthful PASS and false FAIL. These are descriptive pilot results, not a population effect or part of the 40-episode denominator.

The larger research question is **“Can a wrong verdict undo a security fix?”** The [prospective paired study](docs/INTEGRATED_STUDY_EXTENSION_20261018.md) would change the verdict while holding the verified candidate fixed. A separately proposed second-opinion experiment would test whether an optional independent check helps the agent preserve that finite property. These are proposed experiments; the historical audit above is the completed result.

## Manuscript and status

The [research article](paper/final.md) is available as [identified PDF](paper/submission/full_paper.pdf), [identified DOCX](paper/submission/full_paper.docx), [anonymous PDF](paper/submission/full_paper_anonymous.pdf), and [anonymous DOCX](paper/submission/full_paper_anonymous.docx). It has a 234-word abstract, six figures, four tables, 27 cited sources, and 16 A4 pages in each PDF. The [dated author-review bundle](paper/AUTHOR_REVIEW_BUNDLE_20261005.md) binds an earlier manuscript snapshot, derived results, and two independent receipt audits; its hashes should not be used for the current rendered files. The current article remains **`REVIEW_ONLY`**. Author approval, declarations, venue selection, data availability, and privacy review are recorded in the [submission decision form](paper/AUTHOR_SUBMISSION_DECISIONS_20261005.md).

The **prospective v1 main study is `NOT_READY`**: its [12-point release gate](docs/MAIN_RELEASE_GATE_MATRIX_20261005.md) currently passes none of the checks, and it has **zero eligible main episodes**. The proposed 600 full episodes plus conditional C5 continuations are a plan, not collected data. Excluded pilots cannot be relabeled as main results. See the [current action list](docs/NEXT_READY_ACTIONS_20261008.md) and [research status](FINAL_RESEARCH_STATUS.md). Older dated plans in `docs/` describe earlier project states; use these current records for decisions.

The [integrated study extension](docs/INTEGRATED_STUDY_EXTENSION_20261018.md) describes how the historical audit, a prospective corrected-oracle experiment, and separately analyzed executable-code checks can form one expanded research article. It proposes a prespecified finite-property regression outcome for the C5 matched continuations; no prospective result is claimed.
The [18 October engineering checkpoint](docs/INTEGRATED_ENGINEERING_CHECKPOINT_20261018.md) records the implemented collectors, candidate checks, real-model rehearsals, full-test limitation, and exact release blockers.
The [verified excluded v7 R1/C5 case](docs/EXCLUDED_V7_R1_C5_PAIRED_CASE_20261018.md) links the in-repository precursor and matched continuation archives. It is one pilot pair, not a main-study effect estimate.

## Reproduce locally

From the repository root:

```sh
python3 -B -m analysis.paper_pipeline --output paper/artifacts
sh reproduction/render_paper.sh
python3 -B -m experiments.main_orchestrator main-gate
```

The first command reconstructs historical results from saved local logs and receipts without calling the model or Docker. The second rebuilds the article and figures. The third is a read-only check that currently exits with `NOT_READY`; it does not launch a main run. [Detailed reproduction instructions](reproduction/README.md) explain required inputs and limits. Saved experimental runs, archives, and derived files may contain local metadata; their presence in a Git checkout is not scientific validation or journal data-release approval.

## Repository map

| Path | Contents |
| --- | --- |
| `benchmark/`, `crypto_target/`, `web_target/` | Task definitions, reference implementations, retrieval material, and finite tests. |
| `agent/`, `sandbox/` | Agent adapter and bounded candidate runtime. |
| `experiments/` | Protocols, schedules, saved runs, receipts, and source archives. |
| `analysis/`, `reproduction/` | Analysis and integrity checks. |
| `paper/` | Manuscript, figures, derived data, and submission drafts. |
| `docs/` | Current decision records and dated engineering reports. |

For a short Russian explanation, read the [research findings](docs/RESEARCH_FINDINGS_RU_20261005.md) and the [READY action list](docs/NEXT_READY_ACTIONS_20261008.md).
