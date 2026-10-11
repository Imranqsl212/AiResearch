# Prospective main release evidence matrix — 5 October 2026

The read-only `main-gate` on the [v5 proposed schedule](PROPOSED_MAIN_SOURCE_ARCHIVE_20261005.md)
reports **12/12 checks false**, zero model calls, and zero eligible episodes.
The gate in [`main_orchestrator.py`](../experiments/main_orchestrator.py)
intentionally hardcodes live checks false until a separately reviewed,
main-capable release path and its evidence exist. Passing an excluded fixture
or pilot never changes these fields.

| Gate field | Evidence needed for a future release review | Current evidence and gap |
| --- | --- | --- |
| `static_freeze` | Reviewed clean source commit, exact artifact hashes, final manifest-only freeze, and matching runtime/safety identities. | [Static preflight](../reproduction/preflight.py) rejects the draft manifest and dirty tree. |
| `schedule_integrity` | Final source-bound 600-episode schedule with conditional C5 reservation, frozen seed, and exact hash in the root manifest. | [v0.3 schedule contract](FINAL_MAIN_SCHEDULE_CONTRACT_20261005.md) passed in a temporary Git test; the saved v5 proposal is ungated and has no root freeze. |
| `main_collector_capability` | Independently reviewed, fail-closed collector that can produce eligible `main` episodes only after every release check passes. | The v1 collector refuses `main`. [Excluded collector](MAIN_COLLECTOR_SCAFFOLD_20261005.md), [C5 fork](MAIN_C5_FORK_SCAFFOLD_20261005.md), and [dispatch](MAIN_LIVE_DISPATCH_EXCLUDED_20261005.md) exercise only pieces with pilot/fixture status. |
| `fresh_safety` | Safety receipt for the exact final image, policy, daemon, model/tool configuration, and source revision. | The earlier 11-check pass is for its own saved runtime identity, not a frozen main release. |
| `oracle_validation` | Independent feasibility/security-oracle review for the chosen 20-family version, including C3/C4 proofs and evaluator disagreement semantics. | [v6 blocker](BATCH_C_SEMANTIC_ADMISSION_BLOCKER_20261005.md), [v7 candidate](BATCH_C_V7_SEMANTIC_CANDIDATE_20261005.md), and [pending v7 human forms](V7_HUMAN_ADMISSION_REVIEW_PACKET_20261005.md); zero admitted. |
| `mutation_validation` | Strong/weak evaluator and adversarial mutation results on the final admitted task set, independently checked against the oracle. | Existing finite and two real-code calibrations are narrower than a frozen final-set validation. |
| `model_freeze` | Exact primary model name/digest, provider/runtime, decoding options, token and timeout budgets; any comparison models specified before results. | The v5 proposal uses planning placeholders. |
| `pilot_replay` | Excluded engineering replay on the **final** source/runtime/configuration, with failures and invalidations retained. | Earlier replay receipts concern earlier code and pilot-only paths. |
| `logging_integrity` | Complete per-action request, response, candidate, feedback, oracle and stop receipts with write-once invalidation handling and independent replay. | [Excluded raw C5 reader](C5_RAW_ARCHIVE_READER_20261005.md) and [dispatch recorder](MAIN_LIVE_DISPATCH_EXCLUDED_20261005.md) test portions on fixtures; no complete live main trace. |
| `request_archive` | Proven exact pre-dispatch request bytes, raw return bytes, model identity, and source binding for every scheduled slot, including interrupted calls. | Excluded [recorder](MAIN_LIVE_DISPATCH_EXCLUDED_20261005.md), [loopback transport](MAIN_OLLAMA_TRANSPORT_EXCLUDED_20261005.md), and [read-only crash audit](EXCLUDED_LIVE_DISPATCH_CRASH_AUDIT_20261005.md) pass fixture checks. Real provider execution, process liveness, and external attestation remain unverified. |
| `blind_annotation_plan` | Frozen observable-action codebook, sampling, two independent raters, disagreement resolution, and agreement analysis plan before opening main outcomes. | The final annotation plan is not approved; actual blinded labels belong after collection. |
| `statistical_plan` | Frozen primary estimands, family-level uncertainty, invalidation/missingness rules, conditional C5 analysis, multiplicity and sufficient power decision. | [Preregistration](preregistration_v1_20261005.md) and a [NON_READY analysis candidate](STATISTICAL_ANALYSIS_PLAN_CANDIDATE_20261005.md) specify methods, but the meaningful effect, power target, assumptions, reader, and final-schedule binding remain unapproved. |

In parallel, [R1 v0.2 source review](R1_V2_SOURCE_REVIEW_PACKET_20261005.md)
has 40 pending reviews and 20 pending adjudications. Admission of the exact
retrieval corpus and privacy disposition must precede its final binding.
These are evidence tasks, not flags to edit in the draft manifest. After
the scientific and technical reviews, run a fresh release audit and only then
enable prospective collection. No excluded observation can be relabeled.
