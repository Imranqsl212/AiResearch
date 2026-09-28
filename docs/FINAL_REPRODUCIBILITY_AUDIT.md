# Final reproducibility audit — When to Stop

**Audit date:** 2026-09-29. **Verdict:** protocol and zero-data audit are reproducible in this local snapshot; a publication-quality *empirical* reproduction is **BLOCKED** because the main experiment is absent and the runtime safety gate has not passed. No raw trajectory was edited during this review.

Statuses below distinguish a passing check from an unperformed or inapplicable empirical test. A unit-test pass is not a substitute for an independently run AI agent or an approved Docker target.

| Requested check | Status and evidence |
| --- | --- |
| Repository builds | **PARTIAL.** Python 3.14.6 imports and runs the local test suite. There is no packaged build/release contract for this study. An approved container image has not been built or pinned; no full experimental build claim is made. |
| Tests pass | **PASS for unit tests:** `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v` ran 33 tests, all passed. Two new tests protect against zero-data audit clobbering a locked/candidate analysis. |
| Docker works | **PARTIAL.** A host Docker daemon was reachable in a read-only elevated check (server 29.1.3). This confirms host availability, not task-image build, isolation, or safe agent execution. |
| Safety tests pass | **FAIL-CLOSED / NOT PASSED.** [Latest receipt](../sandbox/safety_checks/latest_result.json): static policy `PASS`; nine runtime containment probes `NOT_RUN_FAIL_CLOSED`; `overall_passed: false`; `experiment_permitted: false`. The approved immutable image list is empty. No experiment may run. |
| Benchmark validates | **PASS for the static pilot only.** `python3 -B -m benchmark.quality --json`: nine task contracts pass, three per `SOLVABLE`, `DISTRACTOR`, `UNSOLVABLE`; `agent_runs_launched: 0`. Executable task realism and the four-cell confirmatory suite are **NOT IMPLEMENTED**. |
| Agent runner works | **PARTIAL.** A deterministic scripted integration fixture tests the adapter/logging path; no provider-backed agent is configured or evaluated. |
| Verifier works | **PARTIAL.** Finite-state reference-plan and verifier unit tests pass; the eight-record scripted fixture contains a verifier-confirmed terminal state. An independent executable-target verifier audit is **NOT DONE**. |
| Analysis reproduces tables | **PASS only for the availability audit.** `python3 -B -m analysis.pipeline --json audit` returns zero eligible main runs, one excluded fixture, and an input inventory. The locked analysis path is exercised by synthetic unit tests but no real table can be regenerated. |
| Analysis reproduces figures | **NOT APPLICABLE to empirical figures.** [Figure manifest](../figures/stopping_experiment/figure_manifest.json) withholds all planned plots because there is no eligible main input; synthetic tests can generate figures but are not evidence of an experiment. |
| Paper numbers match analysis | **PASS for the limited numbers actually reported.** Nine pilot tasks come from `benchmark.quality`; zero eligible runs/zero clusters and one excluded fixture come from [analysis/results.md](../analysis/results.md); eight fixture records come from the [artifact validator](../experiments/validate_artifacts.py); transition counts 3/5/4 and the common six-step cap/branching factor two come from all nine `benchmark/tasks/pilot/*.json`. No behavioral rate appears in the paper. |
| Citations are real | **PASS for the final paper's ten listed items.** Titles/authors and URLs were checked against the primary ICLR proceedings or author-hosted arXiv records; the CyberGym BibTeX title was corrected. The broader legacy/project bibliography was not exhaustively revalidated here. |
| No fabricated claims | **PASS within the auditable manuscript.** It reports engineering status only, explicitly labels agent behavior not estimable, and does not repurpose AVB-Bench or scripted-fixture outcomes. This is a review judgment, not proof about every legacy document in the workspace. |
| No unexplained results | **PASS for this manuscript:** no empirical behavior result or effect size is claimed. The absence of eligible trajectories is explained by the inventory and execution report. |
| Git state clean/documented | **BLOCKED / DOCUMENTED.** `git status --short` returns “not a git repository”; there is no `.git` directory and no source commit. Cleanliness, code freeze, and source-history reproduction cannot be verified. The engineering fixture validator warns about unavailable Git provenance. |

## Input integrity and traceability

The sole stored trajectory is `experiments/runs/e2e-local-finite-state-v0.1.2/fixture-run-0001.jsonl`. Its SHA-256 before and after this review is `7de80aa43ed0feefb2ab88f67ec7d634dd4688b583b8fd39db19109b9e310c8b`. The artifact validator reports eight records, no integrity errors, and a Git-provenance warning when `--require-git` is omitted. It is intentionally excluded from all behavioral analysis. With `--require-git`, this fixture should not be treated as a valid main-study artifact.

`analysis.pipeline audit` is intentionally a zero-data status generator. During this audit, a genuine output-integrity flaw was found: it could overwrite previously derived results even when main candidates existed. It now halts before writing if candidate main trajectories require an explicit lock or if prior provenance is not the zero-data audit mode. Synthetic regression tests cover both paths. This is a safeguard for later data, not evidence that later data exist.

The static pilot task metadata has a systematic imbalance: every solvable task declares three transitions, every distractor task five, and every unsolvable task four. All declare two-way branching and six maximum steps. Because condition predicts this structural difficulty proxy, the pilot cannot isolate stopping from task difficulty. The four-cell confirmatory study described in the preregistration is not implemented and cannot be inferred from the pilot.

## Exact local reproduction sequence

Use the first section of [README.md](../README.md) for commands and expected outputs. The decisive commands were the 33-test suite, static benchmark quality check, fixture manifest/log/receipt validation, analysis input audit, and SHA-256 digest of the fixture. The runtime safety suite and its receipt were inspected separately; its nonzero result is a blocker, not a test failure to ignore. No main experiment or public target was run.

For a future empirical reproduction, a researcher would additionally need: a version-controlled source revision, pinned dependencies and Docker image digest, frozen preregistration and task/verifier set, a model/harness revision and configuration, all immutable raw trajectories and receipts, human adjudication records and reliability estimates, an explicit analysis input lock, and regeneration of every table and figure. None of those missing empirical materials can be reconstructed from the current zero-data audit. If externally stored completed runs are later supplied, validate their hashes, source provenance, safety receipts, and protocol compatibility before writing any empirical paper.
