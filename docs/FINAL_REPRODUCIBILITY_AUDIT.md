# Final reproducibility audit — 2026-09-29 hardening worktree

> **Historical audit.** For the completed 2026-10-02/03 exploratory cohort and
> paper reproducibility review, see [PAPER_SUBMISSION_AUDIT.md](PAPER_SUBMISSION_AUDIT.md).
> The findings below refer to the earlier hardening worktree.

**Verdict: NOT READY for empirical reproduction.** The repository now has an auditable source baseline and a reproducible engineering-only fixture, but no eligible agent trajectory, clean experimental freeze, approved image, passing runtime safety suite, or completed confirmatory pipeline. This audit reports checks at their actual scope; it does not convert an unrun containment test into a pass.

## Source and environment

- Audit-start HEAD: `8d5bcac786bfd9a75f7a60b1ed3bbe8be1d15086`. The hardening worktree is modified and **not frozen**. A final study must commit and verify a clean source tree before collection.
- Python: 3.14.6. The local Python test path uses the standard library; provider SDK, full dependency lock, and real-agent runtime are **NOT IMPLEMENTED**.
- The tracked pre-Git scripted fixture remains an excluded engineering artifact; its SHA-256 is `7de80aa43ed0feefb2ab88f67ec7d634dd4688b583b8fd39db19109b9e310c8b`. It was not edited or promoted to scientific data.
- A local candidate image digest is documented in [image_provenance.md](image_provenance.md), but the official image allow-list is empty. The current runner policy differs from the historical candidate attempt; that attempt cannot approve this policy.

## Verification matrix

| Requirement | Current result |
| --- | --- |
| Repository builds | **PARTIAL:** Python modules import and local tests run; there is no packaged experimental build contract. |
| Unit, failure-injection, and synthetic tests | **PASS locally:** `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -q` ran 120 tests, all passed. This is not a runtime containment or model evaluation. |
| Docker daemon | **PARTIAL:** an earlier read-only elevated query reached the local daemon and reported seccomp/cgroupns but no userns remapping. The latest official suite could not access the socket in this permission profile. No current-policy container launched. |
| Complete safety suite | **FAIL-CLOSED / NOT PASSED:** [latest receipt](../sandbox/safety_checks/latest_result.json) has static policy `PASS`, nine runtime checks `NOT_RUN_FAIL_CLOSED`, `experiment_permitted=false`, and no approved image. |
| Benchmark validation | **PASS only for static contracts:** nine v0.1.1 finite-state tasks, three per condition. The quality output also reports `difficulty_matched_by_transition_count=false`; executable reachability and distractor plausibility remain unverified. |
| Agent runner | **PARTIAL:** scripted in-memory fixture and failure-injection tests pass. Provider-backed and Docker-backed adapters are **NOT IMPLEMENTED**. |
| Independent verifier | **PARTIAL:** authored finite-state oracle edge tests, concordant terminal receipts, and completed-prefix action receipts pass. Independent **executable-target** action/terminal verification and alternate-path review are **NOT IMPLEMENTED**. |
| Artifact integrity | **PARTIAL:** event order, unique IDs, receipt/manifest experiment identity, verifier contradictions, raw hashes, exactly one RD/UD/RW/UW task per main family, and a synthetic-tested seeded schedule/all-attempt ledger lock are checked. The main input lock requires per-action receipts in non-aborted runs; old fixtures remain optional/explicitly excluded. A metadata-only reservation/completion writer now emits a lock-compatible ledger and fails closed on unresolved attempts. Provider orchestration, an actual frozen main schedule, full typed schema/provenance, immutable archive, and recovery of attempts with no raw log remain incomplete. |
| Analysis tables and figures | **ZERO-DATA PASS only:** `analysis.pipeline audit` returns `NO_ELIGIBLE_DATA`, one excluded fixture, and no empirical figure. Synthetic temporary locks exercise generation code but do not validate real inference. |
| Statistics | **NOT READY:** H1 descriptive RD/UD/CPS family summaries and zero-filled incomplete-cell sensitivity now pass synthetic tests, but H1 GEE, model-first H2/H3, broader nonignorable-missingness analyses, and a predeclared confirmatory dataset do not exist. The deterministic synthetic family-t power *proxy* was reproduced byte-for-byte (saved SHA-256 `9419e138004e85854998efc0f8fe3debe5930cb7ce424c51dbf78d50f442cc65`), but it is not the preregistered GEE power gate; exploratory matched checks cannot substitute for confirmatory tests. |
| Paper numbers | **PASS at engineering scope:** nine tasks and zero eligible trajectories trace to static validation and the input inventory. No agent-behavior rate, p-value, or effect size is reported. |
| Citations and all legacy documents | **PARTIAL:** the earlier manuscript audit checked its ten listed primary references. Two newly added small-cluster methods references were checked against their primary publication records and added to the bibliography/matrix; the complete legacy bibliography was not revalidated in this pass. |
| Git state | **DOCUMENTED, NOT CLEAN:** the repository has a baseline commit and intentional hardening changes. No real run is attached to this uncommitted tree. |

## Replay and limits

A new scripted v0.1.1 fixture was previously generated in a disposable temporary directory under a distinct engineering experiment ID. Its eight-event semantic action/outcome sequence matched the tracked fixture after normalizing IDs, timestamps, and version fields. Its manifest/log/receipt passed the local artifact validator with a concrete Git revision; `--require-git` alone does **not** prove that the worktree was clean. A separate **v0.1.3** in-memory fixture was then generated in a disposable directory after the action-verifier change: its eight-event log has two ordered evaluator-only action receipts (`VALIDATED_NON_SUCCESS`, then `VALIDATED_SUCCESS`) and passes `validate_artifacts --require-action-verifier`. This new fixture is not part of the research dataset. The raw tracked v0.1.2 fixture hash remained unchanged.

The zero-data analysis audit produced `NO_ELIGIBLE_DATA` and withheld empirical charts. This is the correct output for the current workspace, not a measured zero success or stopping rate. To reproduce an eventual study, another researcher will need a clean committed freeze, source/dependency/provider versions, signed-off image and daemon fingerprint, complete runtime safety receipt, task/verifier hashes, schedule and exclusion ledger, immutable raw trajectories, evaluator-owned action-timed and terminal receipts, blinded coding, and a locked analysis input set. Until those exist, empirical reproduction is **NOT POSSIBLE**.

The current v0.1.4 disposable in-memory fixture additionally produced a
**nine-event** log with `TASK_HANDOFF_START` before task provision and passed
strict artifact validation with two action receipts. This did not change the
tracked historical fixture or create an eligible model run. The attempt-journal
writer's create-once semantics were exercised only on synthetic temporary data;
an interrupted attempt with no valid raw log still cannot be finalized without
an explicit future recovery protocol.
