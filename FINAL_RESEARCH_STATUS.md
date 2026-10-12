# Research status — 5 October 2026 (dated snapshot)

This record preserves the 5 October research assessment. For the current
repository overview and manuscript status, use [README.md](README.md) and the
[main release gate](docs/MAIN_RELEASE_GATE_MATRIX_20261005.md). The later
research branch tracks saved raw episodes and archives; Git availability
does not change their cohort eligibility or constitute journal data approval.

**Current verdict: prospective v1 NOT_READY; zero eligible main episodes.**
The [5 October readiness decision](docs/READINESS_UPDATE_20261005.md) supersedes
the dated baseline below. A 40-slot, 20-family live feasibility block produced
30 valid excluded episodes, 10 invalidations, and 14 agent-generated secure
onsets in 10 families. [All 14 onset forks](docs/C5_ALL_ONSETS_EXCLUDED_AUDIT_20261005.md)
completed without invalidation: early voluntary stops were 3 after truthful
PASS and 0 after false FAIL, while later candidate submissions were 28 versus
17. These are selected, descriptive engineering results, not a prospective
main effect. A separate [20-family R1 live feasibility block](docs/R1_TWENTY_LIVE_FEASIBILITY_20261005.md)
assigned 40 C2 R0/R1 slots, retained two invalidations and yielded 19
complete pairs: 12 both secure, six neither secure, one R0 only and zero R1
only. Its unreviewed retrieval corpus and unequal request lengths prevent a
RAG-effect claim. A [source-support spotcheck](docs/R1_SOURCE_SUPPORT_SPOTCHECK_20261005.md)
found citation/task-rule mismatches and answer-cue review questions across
the 20-family candidate; the reviewer register remains pending. The manuscript for the older 40-episode exploratory
audit is available for author review, with [submission gaps](paper/SUBMISSION_HANDOFF_20261005.md)
recorded separately. A [local author-review bundle](paper/AUTHOR_REVIEW_BUNDLE_20261005.md)
packages exact manuscript and result files without private raw archives.
Its [sanitized review candidate](paper/SANITIZED_REVIEW_CANDIDATE_20261005.md)
now recomputes 13 saved result sections from transformed bytes but still needs
privacy/provenance review before release. The root manifest remains a draft and the collector
continues to reject `main`.

A separate [corrected-oracle v7 live pilot](docs/V7_DECISIVE_EXCLUDED_PILOT_20261005.md)
completed **30/30** excluded slots in two authored families: three seeded
repeats of each C1–C5 cell at temperature 0.3. Across six matched C3/C4
seed blocks, candidate-submission counts and early voluntary stopping were
identical. Two C4 voluntary stops occurred only on the last allowed decision.
One selected agent-generated secure onset had a matched C5 continuation:
truthful PASS stopped after one decision; false FAIL used all three and
submitted one further candidate. The [saved audit](analysis/v7_decisive_excluded_audit_20261005.json)
and [fork audit](analysis/v7_decisive_c5_fork_audit_20261005.json) replay the
private source-bound records. Two families and one selected fork do not yield
a population confidence interval or a causal estimate for main.

The [historical source-fidelity audit](docs/EXPLORATORY_SOURCE_FIDELITY_20261005.md)
finds **63/77** logged Python attempts parseable, **11** with syntax-breaking
logger redaction markers, and **three** other malformed strings. The erased
expressions cannot be recovered from the archived logs, so all 77 executed
ASTs cannot be reconstructed. [Future per-action finite check logging](docs/PER_ACTION_CHECK_LOGGING_20261005.md)
now retains each complete structured evaluator receipt or an explicit
no-valid-receipt reason, without changing historical records or opening main.

A [batch-C semantic audit](docs/BATCH_C_SEMANTIC_ADMISSION_BLOCKER_20261005.md)
found that eight current C3/C4 impossibility certificates rely on a shared
`complete_observation=false` gate and schematic witnesses. Their machine
precheck is insufficient for admission; replacement artifacts need independent
review. A separate [v7 candidate](docs/BATCH_C_V7_SEMANTIC_CANDIDATE_20261005.md)
now encodes explicit same-observation conflicts for those eight families but
remains unadmitted and outside main. The agent-task mapping now delivers its
public mode semantics and the shape guard accepts its modes. A separate
[excluded fake-provider integration](docs/BATCH_C_V7_EXCLUDED_INTEGRATION_20261005.md)
routes v7 through the versioned registry and replays its source-bound logs,
but end-to-end main dispatch is still absent. A separate
[R1 v0.2 candidate](docs/R1_TWENTY_CANDIDATE_V2_20261005.md) repairs seven
source paragraphs without changing the excluded v0.1 pilot; its
[22 cited pages](docs/R1_V2_PRIVATE_SOURCE_SNAPSHOTS_20261005.md) now have
private byte snapshots. It has no model observations or human admission. A
[version-bound v0.2 reviewer packet](docs/R1_V2_SOURCE_REVIEW_PACKET_20261005.md)
has 40 pending reviews, 20 pending adjudications, and zero recorded `KEEP`
decisions. A
[v0.3 final-schedule contract](docs/FINAL_MAIN_SCHEDULE_CONTRACT_20261005.md)
now resolves the schedule/root-manifest hash cycle in a temporary Git test,
while [collector](docs/MAIN_COLLECTOR_SCAFFOLD_20261005.md) and
[C5 family-ledger](docs/C5_FAMILY_LEDGER_SCAFFOLD_20261005.md) scaffolds test
excluded fixtures only. A [C5 branch scaffold](docs/MAIN_C5_FORK_SCAFFOLD_20261005.md)
also checks fixture reservation and A/B trace shape, without an independent
live onset oracle. An [excluded precursor bridge](docs/MAIN_LIVE_PATH_CONTRACT_AUDIT_20261005.md)
links scripted precursor and fork archives by saved bytes. None releases main
dispatch or inference. An [excluded C5 raw reader](docs/C5_RAW_ARCHIVE_READER_20261005.md)
checks fixture branch bytes and nonestimability conditions. A separate
[live-dispatch recorder](docs/MAIN_LIVE_DISPATCH_EXCLUDED_20261005.md)
archives requests before injected fake transport and responses before parsing;
an opt-in [loopback transport](docs/MAIN_OLLAMA_TRANSPORT_EXCLUDED_20261005.md)
passes fake HTTP byte/identity tests. No real provider call or independent
oracle was bound. A [read-only crash audit](docs/EXCLUDED_LIVE_DISPATCH_CRASH_AUDIT_20261005.md)
classifies partial excluded slots without retry or main promotion. A
[NON_READY statistical plan candidate](docs/STATISTICAL_ANALYSIS_PLAN_CANDIDATE_20261005.md)
specifies estimands and missingness rules but still needs scientific sign-off,
power decisions and a real main reader.

## Earlier 4 October baseline (retained for audit history)

**Prospective main study: `NOT_READY`.** Twenty controlled finite families are now represented: the original four plus three authored batches. The machine admission pre-review checks 100 C1–C5 task rows, proof hashes, public parity, and declared domain uniqueness, but records human admission as missing. These artifacts still do not supply 20 independently reviewed families or any eligible main observation. [`experiment_manifest.json`](experiment_manifest.json) remains a draft; the main collector rejects `phase="main"`, and [`analysis/v1_pipeline.py`](analysis/v1_pipeline.py) returns `NO_ELIGIBLE_DATA`.

The completed 40-episode legacy cohort is a separate exploratory [benchmark audit](research_audit.md). Its nominal unavailable conditions were implemented with a hidden acceptance veto, so they cannot establish that the task was impossible. Its results are never pooled with prospective v1.

## Verified engineering evidence

| Area | Current evidence | Limit |
| --- | --- | --- |
| Finite tasks and evaluators | The original four versioned mechanisms have five matched C1–C5 pairs each and [1,430 exhaustive checks](docs/FINITE_FIXTURE_CALIBRATION_20261004.md). Batch A adds four families with 140 checks, batch B four with 90, and batch C eight with 160. The [machine admission pre-review](analysis/admission_review_20261004.json) finds no hash, parity, or *structural* proof errors across 20 families and 100 rows, while explicitly recording missing human review. | These are authored finite languages, not population error rates for real software. The [batch-C semantic blocker](docs/BATCH_C_SEMANTIC_ADMISSION_BLOCKER_20261005.md) remains despite the structural pass. No family is human-admitted or main-admitted. |
| Executable-code external validity | The [SQLite injection calibration](benchmark/real_code_sqli_notes.md) and new [command-injection calibration](benchmark/real_code_command_injection_notes.md) each use a separate host oracle and disposable digest-pinned Docker containers. The command fixture checks both returned content and unintended marker-file side effects; secure, vulnerable, and two weak-passing mutation profiles completed and were removed. | These are two hand-authored calibration fixtures with no agent-written repair, no broad repository coverage, and no tamper-resistant oracle claim. |
| Runtime containment | The [official safety receipt](sandbox/safety_checks/latest_result.json) reports **11/11 PASS** and `experiment_permitted=true` for the exact current image, policy, and daemon. | A future frozen main runtime and integrated executable tasks need their own binding and fresh check if any identity changes. |
| Source and retrieval | The [v1 corpus review](docs/RETRIEVAL_CORPUS_REVIEW_20261004.md) checked 20 rows for exact answer and hidden-label leakage. A separate [v2 corpus](docs/RETRIEVAL_CORPUS_V2.md) has 22 source-linked rows, including payments guidance, and deterministic R0/R1/R2 tests. | Source URLs are not pinned page snapshots; semantic contamination and input-length controls remain open. The live RAG blocks used v1, not the new v2 corpus. |
| Planning and analysis | A [family-sign sensitivity calculation](docs/FAMILY_SIGN_SENSITIVITY_20261004.md) demonstrates why repeated runs are not independent families. Excluded-pilot and RAG reports reconstruct schedules, receipts, and action logs while leaving population rates and causal effects null. | The actual estimands, power simulation, annotation sample, and multiplicity plan are not frozen. |

## Excluded agent observations

- The original [five-condition authorization pilot](docs/V1_IMMEDIATE_LIVE_PILOT_20261003.md) validated 5/5 `qwen3:4b` R0 episodes. A separate [three-seed C1/C2/C4 block](docs/V1_SEEDED_REPLICATION_PILOT_20261004.md) validated 9/9 episodes. These are local trajectories from one finite family, not a main cohort.
- A [scripted C5 handoff](docs/C5_FALSE_FAILURE_PROBE_RESULT_20261004.md) showed that releasing truthful oracle evidence changed one-step assessments. With that audit withheld, the model incorrectly labeled both C3 and C5 as evaluator mismatch. A separate [gate-verdict onset pair](docs/C5_ONSET_PROBE_RESULT_20261004.md) handed the same scripted oracle-secure candidate to truthful-PASS and false-FAIL arms. Both produced two agent decisions; the false-FAIL arm used its full decision budget and resubmitted the same candidate. Neither probe establishes autonomous discovery or a population effect on the number of actions.
- A prescheduled [ten-slot path/replay block](docs/V3_JSON_PROTOCOL_DIAGNOSIS_20261004.md) integrated the second and third families. All five path slots validated. The five replay slots were retained as protocol invalidations after a valid first action; none was replaced. A new JSON prompt in a separate [replay follow-on](docs/V3_JSON_PROTOCOL_V2_RESULT_20261004.md) validated 5/5 fresh slots. No replay slot reached an oracle-secure submission.
- The separate [counter-race v4 block](docs/COUNTER_RACE_V4_LIVE_PILOT_20261004.md) validated 5/5 `qwen3:4b` R0 slots. C1/C2 each reached a secure accepted atomic policy. C5 submitted **three distinct oracle-secure policies**, all three rejected by the deliberately mismatched gate, then ended at the action budget. C3/C4 exhausted the budget with insecure submissions. This is the first live mismatch exposure in a new finite family, on one seed; it is not a general persistence or causal rate.
- A matched [qwen3:4b RAG block](docs/RAG_MATCHED_EXCLUDED_RESULT_20261004.md) validated 9/9 C1/C2/C4 × R0/R1/R2 slots and logged 40 provider requests. The post-run recovered source archive matches all 13 scheduled file hashes, but it was assembled after collection and only the first full request body is independently reconstructable. Retrieval documents were delivered; actual reliance is unknown. R1/R2 input lengths exceed R0, so the single-seed pattern cannot identify a retrieval-content effect.
- A second 9/9 excluded RAG block on `gemma3:4b` logged 13 provider requests. The [cross-model audit](docs/CROSS_MODEL_RAG_EXCLUDED_RESULT_20261004.md) confirms the nine initial requests match after removing only the model field, while four of 13 scheduled source files differ. Qwen's source archive was recovered after its run; Gemma's was archived before its run. Gemma terminated on its first action in all three C1 and all three C4 cells. This contrast does not show understanding of the C4 proof or a model effect. A separate [C2 protocol smoke](docs/CROSS_MODEL_FEASIBILITY_20261004.md) validated; `qwen3:8b` attempts were invalidated by provider timeouts. These checks establish local access to an independent model, not a frozen, strong-model confirmatory replication.

No excluded pilot is promoted to main data. Counts above describe saved cells and authored challenges only; confidence intervals, hypothesis tests, causal contrasts, RAG benefit, model superiority, and domain-general stopping or secure repair are **not estimated**.

## What still blocks READY

The [independent readiness audit](docs/READINESS_BLOCKERS_20261004.md) and
[gate matrix](docs/V1_GATE_MATRIX.md) give acceptance evidence for each gate.
The largest gaps are independent admission review of every family, a broader
executable-code security tier with held-out mutation challenges,
context-controlled and repeated RAG/model comparisons, two independent
strategy annotators, a frozen power-informed analysis, a reviewed raw-data
archive, and the manifest-only main freeze. The newer
[draft preregistration](docs/preregistration_v1_20261005.md) and orchestrator
propose 20 families × five repeats × four R0 core conditions (400 episodes),
plus C1/C2 R1 on the same repeats (200 episodes), and capacity for up to 100
conditional C5 onset pairs (200 branch continuations). This 600-episode
primary-model schedule remains ungated; live C5 branches are not implemented
for main collection. An [excluded C5 structural dry-run](docs/MAIN_C5_STRUCTURAL_DRY_RUN_20261005.md)
has checked allocation of 200 synthetic precursor statuses into the 100 pair
reservations, with zero model calls. It does not validate secure onsets or
enable main dispatch. A separate [proposed main source archive](docs/PROPOSED_MAIN_SOURCE_ARCHIVE_20261005.md)
checks 246 exact task, proof and implementation files while explicitly leaving
R1 unadmitted and main dispatch disabled. A main runner must retain invalidations without
replacement and pass both static and live release checks before collection.

The [static preflight](reproduction/preflight.py) correctly exits 2 on the draft: model, runtime, RAG, statistics, artifact hashes, source revision, nine readiness flags, and safety-receipt binding are not frozen. The current working tree is not a reviewed clean main release or a manifest-only freeze. The official safety pass and excluded pilots cannot substitute for those fields. All planned counts are design targets, not collected main data.

## Reproduction record

[`reproduction/reproduce.sh`](reproduction/reproduce.sh) passes on this
workspace. It validates all 20 finite task families, the 1,820-row combined
calibration, machine admission pre-review, the family-sign artifact, 285
offline unit/integration tests plus six focused real-code regressions, and
methods-only tables. It confirms `NO_ELIGIBLE_DATA` and the expected
`NOT_READY` preflight. The expanded full suite passed **460/460 tests**
with Docker access for the executable-catalog checks; the subsequent v4
author-bundle change passed its eight focused tests. The official 11-check
Docker safety run and live
excluded pilots have separate receipts. Raw pilot logs are tracked in the
current research branch;
the [private excluded-pilot bundle](docs/PRIVATE_EXCLUDED_PILOT_BUNDLE_20261005.md)
now preserves and replays them locally. Independent content review has not
been recorded for a journal data release. The current [paper](paper/final.md) presents the
historical exploratory audit and a separately labeled, excluded v7 feasibility
pilot; neither is a prospective main result.
