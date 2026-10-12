# Research and submission readiness — 5 October 2026

## Decision

**Prospective v1 main study: NOT_READY.** The root
[`experiment_manifest.json`](../experiment_manifest.json) remains a draft,
[`v1_collector.py`](../experiments/v1_collector.py) still rejects `phase="main"`,
and the v1 analysis has zero main-eligible episodes. No pilot below may be
promoted after seeing its outcome.
The [write-once main refusal receipt](../experiments/runs/main_refusal_20261005/main_refusal.json)
records all 12 live gates false, `model_calls=0`, `candidate_runs=0`, and
`eligible_main_episodes=0` (receipt SHA-256
`d33162f93827cf46bca656edae52d62e9ee636d2b747de60f8cc1950e3f8d0ce`).

**Historical exploratory paper: author-reviewable, not yet submission-ready.**
The [manuscript](../paper/final.md), [PDF](../paper/submission/full_paper.pdf),
[DOCX](../paper/submission/full_paper.docx), references, and recomputed tables
are saved. A [deterministic local author-review bundle](../paper/AUTHOR_REVIEW_BUNDLE_20261005.md)
contains the manuscript and derived artifacts without raw archives inside
that filtered bundle. The raw archives are separately tracked in the present
local Git branch; neither Git tracking nor this review bundle establishes
privacy or journal approval. The paper's primary denominator is the
older 40-episode local cohort; the eight-episode AEAD and excluded 30-episode
v7 pilots are described separately, without pooling. Its central
observation is nine of 20 final candidates in nominally unavailable states
that passed raw family tests while the hidden gate rejected them. It cannot
support a causal feedback or model-effect claim. Other later retrieval pilots
and C5 forks are separate excluded evidence, not extra observations in the
historical denominator.

## What was established locally

| Area | Evidence | Boundary |
| --- | --- | --- |
| Finite catalog | 20 families, 100 C1–C5 task/proof rows, machine precheck conditional; [batch B independence mutation tests](BATCH_B_INDEPENDENCE_REVIEW_20261005.md) pass. | Independent human admission remains missing; finite policy artifacts are not unrestricted code repairs. |
| Full catalog live pilot | [40 prescheduled slots](FULL_CATALOG_LIVE_FEASIBILITY_20261005.md): 30 valid excluded, 10 invalidated, 14 secure onsets in 10 families. | One C1 and C2 per family, no retries; timeouts and one malformed action make a population rate unreliable. |
| Corrected-oracle v7 live pilot | [30 prescheduled slots](V7_DECISIVE_EXCLUDED_PILOT_20261005.md) in two finite families, with three seeds per C1–C5 cell at temperature 0.3: 30 valid, zero invalidations. All six matched C3/C4 blocks had equal candidate counts and no difference in early voluntary stopping. One selected secure C1 onset had a valid matched fork: truthful PASS used one decision; false FAIL used three and submitted one more candidate. The [episode audit](../analysis/v7_decisive_excluded_audit_20261005.json) and [fork audit](../analysis/v7_decisive_c5_fork_audit_20261005.json) were rechecked against saved records. | Two authored, unadmitted families and one post-outcome-selected fork cannot establish a family-population confidence interval or main causal effect. Two C4 voluntary stops occurred at the budget edge, not early. All 30 episodes and the fork are excluded from main and the old paper denominator. |
| Agent-onset C5 fork | [All 14 observed onsets were paired](C5_ALL_ONSETS_EXCLUDED_AUDIT_20261005.md): 14/14 valid forks across 10 families. Early voluntary stops were 3 under truthful PASS and 0 under false FAIL; later candidate submissions were 28 versus 17. | The first pair was selected before the other 13 were scheduled; only successful pilot onsets enter, and the shared continuation notice alters ordinary task flow. No prospective effect estimate. |
| R1 coverage and live feasibility | The [20-family v0.1 candidate corpus](R1_TWENTY_CANDIDATE_AUDIT_20261005.md) has a review register; excluded collector/analysis integration passed 40 fake-provider cases. A separate [40-slot C2 R0/R1 live block](R1_TWENTY_LIVE_FEASIBILITY_20261005.md) produced 38 valid slots and two retained invalidations. Nineteen complete family pairs had 12 both-secure, six neither-secure, one R0-only and zero R1-only outcomes; 15/19 had identical submitted candidate-hash sequences. A [primary-source spotcheck](R1_SOURCE_SUPPORT_SPOTCHECK_20261005.md) identified concrete citation and task-rule mismatches. | One seed and one condition per family, with 306–462 extra UTF-8 bytes in R1's first request. Candidate source support, relevance and semantic leakage lack independent approval; v0.1 source snapshots remain unpinned. This does not estimate a retrieval benefit and does not bind the main retrieval contract. |
| R1 source repair | A separate [v0.2 candidate](R1_TWENTY_CANDIDATE_V2_20261005.md) revises seven source paragraphs and keeps the v0.1 live-pilot inputs byte-pinned. Its new corpus and manifest pass offline checks. [Private snapshots](R1_V2_PRIVATE_SOURCE_SNAPSHOTS_20261005.md) pin all 22 cited URL response bodies; a separate [version-bound human review packet](R1_V2_SOURCE_REVIEW_PACKET_20261005.md) has 40 pending reviews and 20 pending adjudications. | No model run used v0.2. The snapshots need source-claim and privacy review; two NIST captures are landing pages rather than linked PDFs. The corpus remains unreviewed and unbound to main. |
| Request/source provenance | Excluded collectors saved provider requests before dispatch and source/task hashes; the full-catalog and R1 blocks have pre-dispatch source archives and replayed first prompts. C5 preflight hashes match its later copied source archives. | The main release gate is still closed. Local hashes are not third-party timestamps; C5's postrun archive is not a pre-run attestation. |
| Excluded-pilot raw replay | A [historically named private bundle](PRIVATE_EXCLUDED_PILOT_BUNDLE_20261005.md) preserves 1,371 raw/source/audit files and independently replays the full-catalog, C5 and R1 descriptive counts. | The bundle is tracked in the present local Git branch and contains unredacted local paths, prompts and provider responses; no independent privacy review is recorded. It is not a prospective main archive. |
| Paper reproduction inputs | Original 311 hashed inputs have a byte-checked archive now tracked in the local branch. A separate [sanitized review candidate](../paper/SANITIZED_REVIEW_CANDIDATE_20261005.md) has per-file old/new hashes and recomputes 13 saved result sections and all 86 submitted source hashes from transformed bytes. An inspection packet locates eight residual path candidates and 457 lexical review leads. | Original exposes local paths; the sanitized copy does not revalidate the original hash chain and still needs human privacy/content review for journal suitability. Git tracking alone is not that review. |
| Historical source fidelity | A [post hoc audit](EXPLORATORY_SOURCE_FIDELITY_20261005.md) rechecked all 77 logged Python attempts: 63 parse as logged, 11 contain unquoted logger redaction markers, and three have other syntax errors. Of 37 adjacent pairs, 25 have two parseable logged sources; none of those 25 has an identical normalized AST. | The 11 erased original expressions are not recoverable from the saved logs. This cannot become an exact AST analysis of all 77 executed submissions; historical records and manuscript denominators remain unchanged. |
| Future per-action checker logging | The [excluded v1 collector contract](PER_ACTION_CHECK_LOGGING_20261005.md) now fsyncs the full structured finite evaluator receipt and digest for each completed starter/submission/check, or records an explicit no-valid-receipt reason. Offline reader replay verifies full receipts; a stale executable sandbox receipt can no longer attach to later `inspect`/`terminate`. | This does not produce per-case process stdout, retrofit old records, implement a verified main oracle, or open the main gate. |

The [100-slot full catalog scripted rehearsal](FULL_CATALOG_REHEARSAL_20261005.md)
remains excluded and had 100 valid integration traces, zero main-eligible
episodes. It checks plumbing, not model behavior. The official Docker
candidate runtime safety receipt from 4 October passed 11/11 for its exact
image/policy/daemon combination; the present 40-slot finite pilot used the
host-side local Ollama provider and finite evaluator, and does not itself
admit executable code tasks for main.

## Gates before a confirmatory READY decision

1. **Independent benchmark admission:** complete the two-reviewer [human
   register](human_admission_review_register_20261005.csv) and separate
   [adjudication register](human_admission_adjudication_register_20261005.csv)
   for all 20 families. The [structural validator](../analysis/validate_human_admission_register.py)
   currently reports 40 pending reviews, 20 pending final decisions, and zero
   admitted families. Real experts must resolve proof independence, overlap,
   leakage, and external validity before any family is frozen. A targeted
   [batch-C semantic audit](BATCH_C_SEMANTIC_ADMISSION_BLOCKER_20261005.md)
   found that all eight C3/C4 proofs depend on a shared
   `complete_observation=false` gate and schematic contradiction witnesses.
   A [separate v7 semantic candidate](BATCH_C_V7_SEMANTIC_CANDIDATE_20261005.md)
   now supplies explicit world/observation conflicts and passes 130 finite
   candidate checks. Its adversarial audit separated eight unsafe-accept
   modes from seven denial-only modes and three wrong-output KDF modes in C1.
   The public mode semantics now survive agent-task mapping. An
   [excluded fake-provider integration](BATCH_C_V7_EXCLUDED_INTEGRATION_20261005.md)
   routes v7 through the versioned registry and replays its fixture logs. A
   separate [30-slot live excluded pilot](V7_DECISIVE_EXCLUDED_PILOT_20261005.md)
   has model calls and complete saved audits, but no main eligibility. V7 still needs independent review,
   corpus alignment, and a
   later source freeze; a signature on the v6 proof is insufficient.
   A separate [v7 reviewer packet](V7_HUMAN_ADMISSION_REVIEW_PACKET_20261005.md)
   keeps its 40 blank reviews and 20 blank adjudications distinct from the
   v6 forms.
2. **One frozen design:** the draft
   [preregistration](preregistration_v1_20261005.md) and proposed
   [`main_orchestrator.py`](../experiments/main_orchestrator.py) now agree on
   600 full episodes for one primary model plus capacity for 100 conditional
   C5 onset pairs (200 branch continuations). This plan is still ungated and
   cannot execute those branches. An [excluded structural dry-run](MAIN_C5_STRUCTURAL_DRY_RUN_20261005.md)
   accounts for 200 synthetic precursor statuses and the 100 reservations,
   with zero model calls or semantic onset checks. Freeze the primary outcome,
   family-level uncertainty, missingness rules, model/retrieval strata, contrasts, and
   power decision before any eligible run. A [NON_READY statistical plan candidate](STATISTICAL_ANALYSIS_PLAN_CANDIDATE_20261005.md)
   specifies family-level estimands, invalidation and missingness handling,
   and C5/Holm rules, while leaving scientific sign-off and calibrated power
   decisions open. The [pilot-informed synthetic sensitivity](../analysis/c5_pilot_informed_sensitivity_20261005.md)
   gives 0.558–0.849 simulated detection probability for a hypothetical
   20-point C5 stopping effect across its reach/loss scenarios; this is not
   calibrated power or a READY pass. An [excluded C5 family-ledger scaffold](C5_FAMILY_LEDGER_SCAFFOLD_20261005.md)
   checks synthetic precursor, reservation, invalidation, and `D_f`
   accounting. A separate [raw archive reader](C5_RAW_ARCHIVE_READER_20261005.md)
   verifies fixture branch bytes and marks analyses nonestimable when valid
   family coverage or variance is insufficient. Neither has read eligible
   main branches.
3. **Live main path:** the excluded provider-backed R1 rehearsal now checks
   source, task, retrieved-document and first-request bindings. A separate
   [proposed main source archive](PROPOSED_MAIN_SOURCE_ARCHIVE_20261005.md)
   verifies 246 exact files and the 600/100/200 plan while keeping dispatch
   disabled and the R1 candidate unadmitted. A separate
   [v0.3 final-schedule contract](FINAL_MAIN_SCHEDULE_CONTRACT_20261005.md)
   resolves the schedule/root-manifest hash cycle in a temporary Git test;
   no project freeze was made. An [excluded scripted trace recorder](MAIN_COLLECTOR_SCAFFOLD_20261005.md)
   checks six-decision and request/response archiving mechanics but cannot
   call a model or supply verified oracle feedback. A separate
   [fixture-only C5 fork scaffold](MAIN_C5_FORK_SCAFFOLD_20261005.md)
   checks reservation, onset receipt, branch parity and three-decision
   accounting from caller-supplied bytes; it does not independently verify
   the onset oracle or live dispatch. An [excluded precursor bridge](MAIN_LIVE_PATH_CONTRACT_AUDIT_20261005.md#new-excluded-linkage-check)
   links a scripted precursor trace to its fork by exact archived bytes. An
   [excluded live-dispatch recorder](MAIN_LIVE_DISPATCH_EXCLUDED_20261005.md)
   fsyncs exact requests before fake transport dispatch and archives responses
   before parsing. An opt-in [loopback Ollama transport](MAIN_OLLAMA_TRANSPORT_EXCLUDED_20261005.md)
   passes exact archived bytes through fake HTTP tests, but no real model call
   or independent oracle was made. A [read-only crash audit](EXCLUDED_LIVE_DISPATCH_CRASH_AUDIT_20261005.md)
   classifies incomplete private slots without retrying or claiming the send
   outcome from a pre-dispatch receipt alone.
   Independently
   approve the corpus and families, implement and test the complete gated main
   path (including conditional C5 branches), bind the exact frozen runtime and
   fresh safety receipt, then make a reviewed clean source commit and
   manifest-only freeze. Only after all gates pass should the collector be
   enabled for prospective main episodes.
4. **Population data and analysis:** collect every prescheduled slot with
   invalidations retained, execute the preregistered matched C5 controls,
   obtain blind strategy annotations and agreement, compute the frozen
   family-cluster analyses and sensitivity bounds, and independently check
   the raw data archive. The selected 14-pair C5 pilot cannot substitute for
   this.

## Gates before submitting the existing exploratory paper

At the time of this 5 October update, the [submission handoff](../paper/SUBMISSION_HANDOFF_20261005.md) included
identified 16-page and anonymous 15-page A4 PDF review copies, with paired
DOCX files at 12 pt and single spacing, and the author-provided name, location,
and email on the identified
title page. The [decision form](../paper/AUTHOR_SUBMISSION_DECISIONS_20261005.md)
records exact hashes and remaining decisions: contribution wording,
funding/conflicts/acknowledgments (the author will clarify these separately),
journal article type and style, data availability, privacy sign-off, and final
scientific approval. Later manuscript renders can have different page counts;
the current files and counts are in [paper/README.md](../paper/README.md).
Raw files are already tracked in the local Git branch;
the reviewer still needs to examine privacy and provenance before deciding
whether this package suits a journal. The sanitized candidate can recompute
the paper's path-independent tables; its separate review is unfinished. The
formatted drafts are not an approved journal submission.
