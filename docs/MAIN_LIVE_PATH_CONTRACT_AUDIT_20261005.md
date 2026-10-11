# Prospective main path contract audit — 5 October 2026

**Decision: NOT_READY.** This is a code and evidence audit of the draft
[preregistration](preregistration_v1_20261005.md), the proposed/final schedule
code, the excluded trace and C5 fork scaffolds, the live `v1_collector`, and the
main release analysis. It does not admit any family, corpus, model, or episode.
The final schedule version currently on disk is `0.3.0`; no `0.4.0` schedule is
present. The current main gate keeps all 12 checks false and reports zero
eligible episodes.

## Priority order

| Priority | Implement or decide | Can be done now? | Required acceptance evidence |
| --- | --- | --- | --- |
| 0 | Admit one exact 20-family task/proof/evaluator set, resolving the v6 batch-C semantic blocker and independently reviewing the separate v7 candidate. | Human review required; technical mutation and cross-reference checks can continue. | Two independent reviews and adjudication for every family, exact admitted index/source hashes, scope of each finite property. |
| 0 | Select and review one R1 corpus and source snapshot, including all 20 family paragraphs. | Source snapshots and leakage screens can be prepared now; scientific source/relevance approval requires reviewers. | Pinned primary-page bytes, independent claim and leakage review, main retrieval manifest and provider bound to schedule. |
| 0 | Set the primary model/runtime/decoding identity and power decision. | Candidate configurations and scenario simulations can be exercised now; freeze needs actual model digest and resource decision. | Exact model snapshot and effective seed/randomness check, six-decision/time/token budgets, cost and onset-reach stop/go documented before outcomes. |
| 1 | Reconcile the final schedule, collector, analysis, and source inventories to the **admitted** versions. | Code and excluded tests can be written now; final binding must wait for admission. | One clean source commit, schedule-first/root-manifest-only freeze, schedule hash and source commit verified; no v6/v7 or R1 v0.1/v0.2 ambiguity. |
| 1 | Build a live main-capable episode runner behind the existing closed gate. | Implement and rehearse under `phase=pilot` now. | Exact provider request bytes fsynced before dispatch, raw response archive after dispatch, observed model identity, task/source hashes, independent oracle receipts, all six decisions, no PASS auto-stop, explicit invalidation without replacement. |
| 1 | Bind the first agent-generated secure C1/C2 submission to a randomized C5 pair. | Structural rehearsals and receipt verifiers can be built now; release requires admitted oracle/model and live replay. | Pre-verdict context and candidate bytes, prior-attempt oracle results, concealed family orientation, same branch context/config/seed, three decisions each, branch order/interleaving, all ten precursors and first-five/nonreach accounting. |
| 1 | Extend main release analysis to C5 raw pairs and all scheduled continuation receipts. | Parser and synthetic fixture checks can be written now. | Raw-reader provenance, pair invalidation/reachability ledger, family `D_f`, fewer-than-15 and zero-variance rules, missingness bounds, no pilot records. |
| 2 | Execute and independently audit all scheduled observations, blind code trajectories, and finalize the article. | Only after the prior freeze and live preflight. | 600 full-slot partition plus conditional C5 receipts, annotation agreement, frozen family-level analyses, privacy and author review. |

The independent executable-code external-validity tier needs its own task
admission and safety evidence; it is not part of the finite main count.

## Concrete contract mismatches and missing invariants

1. **Schedule versus scientific catalog.** `ALL_FINITE_INDEXES` in
   [`main_orchestrator.py`](../experiments/main_orchestrator.py) still selects
   `v6_batch_c/index.json`; the newly created v7 index is separate and
   unadmitted. The analysis `MAIN_IMPLEMENTATION_FILES` also requires v6.
   The planned 600/100/200 shape is internally checked, but it cannot settle
   the batch-C semantic admission question.
2. **R1 cannot be a main treatment on this path.** The proposed source archive
   includes R1 v0.1 as an unreviewed candidate; the repaired v0.2 corpus is
   separate. `v1_collector` permits the 20-family candidate provider only for
   excluded collection, and `analysis/v1_pipeline.py` explicitly rejects that
   unreviewed provider for `phase=main`. The planner does not bind an admitted
   20-family R1 provider/source snapshot.
3. **The final schedule has no fixture-runner consumer.** The schedule builder
   emits source-commit-bound version `0.3.0` with status
   `SOURCE_COMMIT_BOUND_SCHEDULE_UNGATED`. Both `main_collector` and
   `main_c5_fork_scaffold`, and the synthetic C5 ledger, accept only the
   ungated proposed `0.2.0` plan/status. Their tests prove fixture mechanics,
   not compatibility with a future final schedule.
4. **The live collector changes the C5 treatment horizon.**
   `v1_collector.collect_episode` hard-rejects `phase=main` and stops on a
   checker `PASS`. It also computes its effective decisions as the minimum of
   task and caller budgets. Those behaviors cannot deliver the preregistered
   six-decision matched episodes and three decisions in *both* C5 branches.
   The new scaffolds count six and three decisions correctly but have no live
   model, evaluator, or independently verified feedback.
5. **Separate archives lacked a shared precursor link.** The excluded trace
   recorder and excluded C5 fork each validated their own bytes, but no reader
   previously showed that the fork used the exact request, response, candidate,
   and plan archived by the selected precursor trace. The new
   [`main_c5_precursor_bridge.py`](../experiments/main_c5_precursor_bridge.py)
   provides this **read-only, excluded-only** comparison for completed valid
   fixtures. It also requires prior scripted submissions to have `FAIL` and
   the selected one `PASS`. Four focused integration tests pass, including two
   cases where both individual archives verify yet their link fails. This
   still cannot prove model generation, oracle truth, or live dispatch order.
   The trace recorder checks frozen request options but does not reconstruct
   the public task, checker feedback, or the conversation carried across all
   precursor decisions. A real runner and independent replay must establish
   those upstream facts.
6. **C5 has no main release reader.** `analysis/c5_family_ledger.py` is
   synthetic-only and pinned to proposed `0.2.0`. The current main release
   path in `analysis/v1_pipeline.py` checks the 600 full-slot partition and
   episode request/source bindings, but does not ingest the 100 C5 pair
   reservations or up to 200 continuation receipts. The primary C5 estimand
   therefore has no evidence-backed main-data path yet.
7. **Final provenance is unestablished.** The v0.3 schedule code can verify a
   clean source commit followed by a manifest-only freeze, but the project has
   no admitted clean revision or final schedule. Neither fixture recorder
   proves that a real provider call followed a saved pre-dispatch request;
   their `model_calls=0` and `eligible_for_main_analysis=false` fields are
   intentional.

## New excluded linkage check

Run `python3 -B -m unittest -v tests.test_main_c5_precursor_bridge`. The bridge
first invokes both archive verifiers, compares their exact plan bytes, locates
the selected numbered submission in the precursor trace, then compares its
saved request/response bytes and canonical candidate hash to the C5 fork
archive. The output says `EXCLUDED_STRUCTURAL_PRECURSOR_LINK_VERIFIED` and
retains `phase=pilot`, `eligible_for_main_analysis=false`, `model_calls=0`,
`semantic_oracle_verification=false`, and `agent_generation_verified=false`.
It rejects invalidated precursor traces; a later live design must specify
timing and attribution for any post-onset technical failure. It does not read
or modify the old pilots and cannot open `phase=main`.
