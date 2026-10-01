# Autonomous hardening and validation — final report (2026-09-29)

## Executive Summary

**Decision: NOT READY.** The current worktree is a draft measurement protocol with engineering-only fixtures, not an empirical AI-agent study. Zero eligible scientific trajectories exist. No real agent, public target, current-policy container, pilot, main run, or smoke test was launched. Code-level safeguards improved, but the official Docker gate is fail-closed: static policy passed, all nine runtime probes did not run, the daemon lacks reported user-namespace remapping, and no image is approved. The manuscript correctly makes no behavioral-rate claim.

## Starting State

Audit-start HEAD was `8d5bcac786bfd9a75f7a60b1ed3bbe8be1d15086`, with a clean tree, Python 3.14.6, 27 passing local tests, nine symbolic pilot tasks, one excluded pre-Git scripted fixture, and zero eligible provider-agent runs. The historical candidate safety probe failed at `docker create` under unsupported `--pid private`; that receipt is not evidence about the revised policy. The separate deep-security scan returned an older, partial AVB-Bench snapshot and was excluded from current-tree sign-off. Details are in [initial audit](OVERNIGHT_INITIAL_AUDIT.md).

## Major Improvements

- The ordinary Docker launch path now requires an exact official passing safety receipt at the final launch point. Candidate access is limited to fixed probes. Source/policy/image-lock and selected daemon fingerprints bind approval; effective privileges, environment and tmpfs are checked before start. `/work` requests unprivileged ownership; host logs are capped, redacted across read-chunk boundaries, and owner-only.
- The pilot's explicit agent-visible unavailability cue was removed in v0.1.1; full public projections are compared within families. The remaining difficulty confound is emitted rather than hidden.
- Analysis requires a frozen index action **and** evaluator-recorded evidence, distinct from all negative-evidence counts. Missing strategy coding breaks comparisons; commands and tool switches do not imply strategy switches. Positive H1/H2 recovery requires ordered, evaluator-origin action-time verification. Observed immediate stops remain non-recoveries, while infrastructure aborts are excluded from behavioral summaries.
- UD justified-stop scoring now requires a frozen exact-action allowlist, at most two post-evidence checks, remaining step budget, full coding and a passing concordant unavailability verifier. Without the contract it is unassessable.
- Manifest/log/receipt validation now checks experiment identity, event order, terminal contradictions, and per-action witness shape. The analysis lock rejects fixture inputs, mismatched task/version/counts, and missing index/UD contracts. No-data audit explicitly returns `NO_ELIGIBLE_DATA`; confirmatory H2/H3 p-values are suppressed while their model-first gate is absent.
- Twelve named synthetic trajectories, sensitivity probes, fault-injection and regression tests were added. Six independent read-only reviewers repeated their review after the main modifications; their remaining objections appear below and in the [hostile review](FINAL_HOSTILE_REVIEW.md).

## Tests Executed

`python3 -B -m unittest discover -s tests -q`; `python3 -B -m benchmark.quality --json`; official `python3 -B -m sandbox.safety_checks.run --json`; `python3 -B -m analysis.pipeline --json audit`; existing and temporary fixture artifact validation; semantic fixture replay comparison; Git diff/status and raw SHA-256 checks. Tests use no real target or provider.

## Tests Passed

120/120 local unit, synthetic, failure-injection and policy tests passed at the latest rerun. All nine v0.1.1 finite-state task contracts passed **static** validation. An earlier temporary scripted fixture produced an eight-event log whose normalized action/outcome sequence matched the tracked fixture. A separate v0.1.3 temporary fixture produced two ordered per-action receipts and passed strict artifact validation. The current v0.1.4 disposable fixture produced a nine-event log with a pre-handoff marker and passed strict validation. The tracked fixture SHA-256 remained `7de80aa43ed0feefb2ab88f67ec7d634dd4688b583b8fd39db19109b9e310c8b`. Zero-data audit returned `NO_ELIGIBLE_DATA` with one excluded fixture and no empirical figure. The current official safety suite's **static policy check** passed.

## Tests Failed

The complete official safety suite exited nonzero by design because prerequisites are absent; **this is a failed gate, not a failed containment probe**. The older candidate preapproval's unsupported Docker-flag failure belongs to the earlier policy. No final local unit-test failure remains.

## Tests Not Run

All nine current-policy runtime containment checks (`NOT_RUN_FAIL_CLOSED`); in-container UID/GID/namespace/workdir probes; a Docker-backed task/verifier; real-agent smoke/pilot/main study; confirmatory H1 GEE and model-first H2/H3 analysis; human blinded coding; task-difficulty calibration and a power simulation of the **exact preregistered GEE decision rule**. A synthetic family-t planning proxy has run, but does not clear that gate. The unrun checks must not be represented as passing.

## Security Findings

Current read-only Docker inspection showed seccomp and cgroup namespaces but no user-namespace remapping. The official image allow-list remains empty, so runtime containment is unverified. The runner now rejects ordinary use of a candidate lock and rechecks approval at launch. Docker/log policy fixes are static/unit-tested only; kernel/daemon escape resistance, effective UID map, `/work` writability, and a complete immutable-image runtime suite remain unknown. No secret was intentionally used or forwarded, and no external target was contacted.

## Benchmark Findings

The nine tasks are declarative finite-state engineering fixtures, three each for `SOLVABLE`, `DISTRACTOR`, and `UNSOLVABLE`. Graph-relative reference paths and unreachability checks pass, but transition counts remain 3/5/4 by condition in every family. Initial routes, invalid-action behavior, route wording and author-controlled observations may themselves cue condition or difficulty. They cannot support condition-effect inference. The draft preregistration proposes a different four-cell `RD/UD/RW/UW` design; no matched confirmatory suite exists.

## Verifier Findings

Terminal success now needs a matching `passed=true` verifier result; success prose alone cannot pass. Fixture oracles reject tested negative, near-miss, malformed and false-claim cases. The in-memory runner now attaches an evaluator-only verified-state receipt to each completed action; the main analysis lock rejects missing receipts in non-aborted runs. The pilot verifier still shares an authored graph and does not inspect an independent executable target. Alternative valid executable routes and unreachability proofs remain NOT TESTED.

## Agent Findings

The provider-neutral adapter boundary and deterministic scripted test double work locally. There is no provider-backed research adapter, pinned model revision, bounded provider-call deadline, subscription/budget schedule, or Docker-backed episode adapter. Opaque pilot IDs are deterministic label hygiene, not contamination-resistant randomization. No claim about AI-agent adaptation or stopping follows.

## Logging Findings

Observable JSONL, append-only receipt hashes, terminal ordering and error paths are locally tested. Fault injection covers adapter, sandbox, per-action and terminal verifier, cleanup and existing-log overwrite failures. A metadata-only append-once attempt journal now produces a lock-compatible all-slot ledger from synthetic logs; provider-integrated collection and an actual main schedule do not exist. Per-action receipts work for the finite-state fixture, but the executable-task verifier path, full typed event validation, recovery of attempts with no raw log, and immutable main-data archival remain incomplete. Docker host log redaction is best effort; no real Docker log was generated under the revised policy.

## Statistical Findings

Task family remains the inferential cluster; actions are never treated as independent samples. A one-family bootstrap interval is withheld, matched families determine paired effects, and incomplete coding is not silently zero. Infrastructure aborts are retained with exclusion reasons and removed from behavioral summaries. Positive H1/H2 recovery is unassessable without action-time evidence; immediate observed non-recovery is zero. A synthetic-tested H1 zero-filled incomplete-cell sensitivity exists. The confirmatory GEE/model-first tests, an exact-test power simulation, broader nonignorable-missingness analyses, and a four-cell interaction estimand are NOT IMPLEMENTED. A [synthetic planning proxy](../analysis/power_simulation.md) exists, but is not the preregistered test. Matched permutation calculations, if ever produced before an amendment/model gate, are explicitly exploratory.

## Reproducibility Findings

The source baseline and candidate image identity are recorded, but this hardening worktree is intentionally dirty and no experiment is frozen against it. A scripted fixture was semantically replayed in a disposable directory; Docker/provider reproduction was not possible. The exact current status and requirements are in [final reproducibility audit](FINAL_REPRODUCIBILITY_AUDIT.md). Legacy AVB-Bench material was moved recoverably to macOS Trash, not discarded, and excluded from the current GitHub scope; see [cleanup record](LEGACY_CLEANUP.md).

## Paper Findings

[The manuscript](../paper/final.md) is now labeled a draft protocol/status report, not a completed behavioral paper. Its engineering counts trace to static validation and the input inventory. It reports no empirical behavior rates, effect sizes, confidence intervals, or p-values. [Claim matrix](CLAIM_EVIDENCE_MATRIX.md) explicitly rejects generalization to AI agents and unsupported safety/benchmark claims. Existing literature references were not newly revalidated in this hardening pass.

## Remaining Risks

Condition/difficulty confounding; graph/oracle circularity; condition cues in action affordances; deterministic public-ID contamination; missing **executable-target** action-time verification and uncalibrated evaluator overhead; untested runtime isolation; missing provider deadline; incomplete main-run schedule/exclusion ledger; incomplete schema/provenance locks; possible data-dependent missingness; no blinded coding, independent reviewers of executable tasks, or population-level agent sampling. Fixed code-level issues are not proof that these risks are resolved.

## Remaining Blockers

P0: reviewed daemon isolation, exact candidate image and full runtime containment pass, then official immutable approval. P1: matched and independently validated executable task families with hidden action/terminal verifiers and reconciled/frozen protocol; production verifier overhead and UD stop contract validated. P2: legitimate bounded provider adapter, clean Git/dependency/provider/image freeze, randomized schedule and all-attempt exclusion ledger. P3: confirmatory statistical implementation and blinded coding plan. None may be bypassed by relabeling the scripted fixture.

## Exact Experimental Readiness

`experiments/readiness.json` is **NOT_READY**; `agent_experiment_permitted=false`; `smoke_test_permitted=false`; scientific run count **0**. The official safety receipt has one static `PASS`, nine runtime `NOT_RUN_FAIL_CLOSED`, `overall_passed=false`, and `experiment_permitted=false`. The [smoke decision](SMOKE_TEST_REPORT.md) is `NOT_RUN`.

## Evidence-Based Claims

The repository implements a versioned finite-state pilot and observable-log path; 120 local tests pass; nine static task contracts pass but are difficulty-confounded; the zero-data analysis refuses to invent results; the sandbox gate blocks execution under current Docker settings. These are engineering observations only.

## Claims That Must Not Yet Be Made

No claim that AI agents fail to give up, adapt effectively, stop rationally, over-persist, or falsely claim success at a measured rate; no claim that the sandbox is runtime-safe, the benchmark is realistic/matched, or the verifier proves executable-target success. No hypothesis has been tested.

## Recommended Next Step

Keep collection blocked. First obtain an independently reviewed local isolation setup and pass every candidate/official runtime probe on the exact image and daemon; in parallel, reconcile the preregistration with matched executable task families, independent verifier and scheduled-run ledger. Freeze those artifacts in a clean commit, then reassess readiness before **one excluded real smoke test**. Do not run the pilot or main experiment until that smoke path is sound.

## Continuation addendum — scheduled-attempt integrity

After the initial 61-test review above, the analysis input lock was advanced to
v0.2.0. It now requires a pre-run seeded family/repeat-blocked schedule, its
manifest SHA-256, a finalized ledger covering **all** planned slots, and every
raw attempt/receipt. At most two retries are accepted, only after a verified
pre-action infrastructure abort. Post-action aborts remain selected outcomes;
missing slots carry explicit reasons; infrastructure controls are separate.
Derived schedule/attempt/infrastructure tables make denominators auditable, and
an entirely missing sample yields `NO_ELIGIBLE_DATA`, not a zero success rate.
Synthetic tests exercise retries, omissions, orphan logs, post-action aborts,
control separation, and lock tampering. This is not a production collection
writer and does not change the `NOT_READY` or zero-scientific-run decision.
The continuation reran the complete local suite: **76/76 passed**; static
benchmark validation passed with the same 3/5/4 difficulty confound;
`analysis.pipeline audit` returned `NO_ELIGIBLE_DATA`; the fixture SHA-256 was
unchanged. The latest official safety invocation again returned nonzero with
one static `PASS` and nine `NOT_RUN_FAIL_CLOSED`; in this permission profile
the Docker socket is inaccessible and the official image list is empty. An
earlier elevated read-only query also reported no daemon user-namespace
remapping. None of these observations establishes runtime containment.

## Continuation addendum — precollection power sensitivity

A dependency-free, deterministic [synthetic simulation](../analysis/power_simulation.md)
now checks a **family-level Student-t planning proxy** for the H1
intersection–union rule. It uses 10,000 synthetic datasets per scenario and
three cross-condition dependence settings. The weakest simulated alternative
scenario has a Monte Carlo 95% lower bound of 0.8503 under the stated,
favorable design assumptions. This is **not** the preregistered small-sample
GEE score test, does not estimate agent behavior, and does **not** clear the
power gate or freeze 32 task families. The saved report reproduced
byte-for-byte; its SHA-256 is
`9419e138004e85854998efc0f8fe3debe5930cb7ce424c51dbf78d50f442cc65`.
The complete local suite now passes **80/80** tests. Static benchmark
validation still reports the 3/5/4 difficulty confound, and the analysis
audit still reports `NO_ELIGIBLE_DATA`.

## Continuation addendum — action-time evaluator receipts

The v0.1.3 **in-memory scripted fixture** now verifies each completed action
against the finite-state oracle before the public observation is returned to
the adapter. Its two ordered receipts record non-success followed by
validated success; a separate distractor fixture confirms that a goal reached
after a refuted route is not backdated to the failed action. The main input
lock requires per-action receipts for non-aborted runs, while the pre-Git
fixture remains readable and excluded. Verifier exceptions preserve the
observed tool result and cause an infrastructure abort. The complete local
suite passes **89/89** tests; the v0.1.3 temp artifact passed strict validation;
the tracked fixture hash is unchanged. This demonstrates *wiring only*:
the pilot oracle shares the authored graph, no executable target or provider
agent has been tested, and evaluator overhead remains uncalibrated. The
finite-state sandbox now deep-copies verifier snapshots so nested event
mutations cannot rewrite later evidence. Machine-readable readiness gates
use only `READY`/`NOT_READY`; incomplete gates remain `NOT_READY`. Safety
and scientific readiness remain `NOT_READY`.

## Continuation addendum — append-once attempt journal and stricter retry boundary

The metadata-only `experiments/attempt_ledger.py` now writes a durable
reservation before an episode ID may be used, validates the raw log and
receipt before appending a completion, and emits a final all-slot ledger
accepted by the existing v0.2 analysis input lock. Synthetic failure
injection covers restart with a pending reservation, duplicate IDs,
retroactive reservation, pre-handoff setup retries, aborts after task
handoff/initial observation/action/stop, three exhausted setup attempts, changed raw receipts,
orphan/partial files, and a mutated manifest. No real agent or container was
run. The retry definition was tightened *before scientific collection*:
`TASK_HANDOFF_START` is now durably logged before `adapter.provide_task`; it
makes an abort non-retryable, preventing a task-exposed attempt from being
silently discarded. This amendment is recorded
in `docs/preregistration.md`.
The runner now also fsyncs `TOOL_CALL` before the adapter callback, so a
callback failure cannot erase an accepted action from the trace. A regression
test checks this ordering; it remains an infrastructure abort, not a measured
agent failure.

The complete local suite passes **110/110** tests; static validation still
passes nine tasks with the unchanged 3/5/4 condition–difficulty confound;
analysis audit still returns `NO_ELIGIBLE_DATA` (one excluded fixture).
The tracked fixture SHA-256 remains
`7de80aa43ed0feefb2ab88f67ec7d634dd4688b583b8fd39db19109b9e310c8b`.
The official safety suite remains **not passed**: static policy `PASS`, nine
runtime checks `NOT_RUN_FAIL_CLOSED`, no approved image. This writer is not
connected to provider orchestration, and an interrupted attempt without a
valid raw log remains unresolved rather than silently rerun. A real frozen
main schedule, immutable raw archive, and collection approval remain absent.

## Continuation addendum — precollection H1 denominator and missing-cell audit

Synthetic failure injection found that a failure-exposed RD run ending with
verified no-goal after adaptation, or ending at a budget/timeout, could be
omitted from H1 rather than scored as observed non-recovery. The metric kernel
now separates terminal *task state* from *stop cause*: a verifier-confirmed
no-goal scores RD recovery zero; an ordered evaluator-confirmed, terminally
retained goal may score recovery before forced termination; a forced UD stop
scores zero for agent-chosen justified stopping. `UNKNOWN` task state and
infrastructure abort remain missing/excluded. Descriptive success likewise
uses the independent task-state receipt and is not negated solely by a forced
end. No main-agent data existed when this preregistration clarification was
recorded.

Analysis v0.3.0 now reports RD and UD component means over their **own**
observed family cells, CPS over complete RD/UD pairs only, and a separate
planned-family zero-filled sensitivity for cells with no eligible exposed run.
These tables and bootstrap intervals are descriptive; the preregistered H1
GEE test remains **NOT IMPLEMENTED**. Synthetic temporary locks and 120/120
local tests pass. Static benchmark validation remains difficulty-confounded;
`analysis.pipeline audit` still returns `NO_ELIGIBLE_DATA` with one excluded
fixture; the official safety suite remains fail-closed with nine runtime
checks unrun. The tracked raw fixture and saved synthetic power report hashes
are unchanged. No behavioral effect is estimated or claimed.
