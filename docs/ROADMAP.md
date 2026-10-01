# Roadmap: When Secure-Code Repair Fails

**Scope:** how a provider-backed AI agent responds to verified cryptographic misuse
feedback in a safe local environment.
**Current state:** benchmark v0.3.0, executable crypto family references, approved
Docker image, and excluded Ollama smoke traces exist; no pilot or main experiment has
been executed.

## Phase 0 — Scope and literature freeze

- [x] Narrow the domain to AEAD, nonce safety, and key management.
- [x] Define the research gap, non-claims, and four-cell design.
- [ ] Freeze the final preregistration and citations.

## Phase 1 — Benchmark construction

- [x] Generate 12 matched declarative tasks: three families × RD/UD/RW/UW.
- [x] Add schema, static quality gate, family balance, and deterministic oracle checks.
- [x] Implement a local executable Go AEAD target and evaluator-only verifier receipts.
- [x] Extend executable reference verification to nonce and key-management families.
- [ ] Validate repairable paths through alternate routes and unavailable paths through
  independent reachability checks.
- [ ] Test that distractor hypotheses are plausible but not the true invariant.

## Phase 2 — Safety and runtime

- [x] Docker Desktop network/credential/host-mount/resource safety checks pass locally.
- [x] Pin and record the approved immutable image.
- [x] Build, self-test, and independently safety-review the crypto target image.
- [ ] Fail closed if any runtime check, image digest, or verifier check changes.

## Phase 3 — Agent and data integrity

- [x] Connect one permitted local provider-style agent through the adapter interface
  (`Ollama/qwen3:4b`).
- [ ] Freeze provider, model ID, agent version, prompt, tools, temperature, budget,
  and rate-limit policy without placing credentials in Git.
- [ ] Integrate provider actions, Docker events, attempt ledger, per-action receipts,
  interruption recovery, and immutable raw archive.
- [x] Run excluded smoke tests and verify complete traces; premature tool-call failure
  is mitigated, but pilot acceptance remains blocked by invalid submissions/timeouts.

## Phase 4 — Pilot

- [ ] Run a predeclared pilot on the 12-task suite or the approved subset.
- [ ] Check task distinguishability, verifier validity, feedback leakage, logging,
  strategy labels, and confounding before any main run.
- [ ] Record every pilot change as a protocol amendment; do not silently alter tasks.

## Phase 5 — Main experiment

- [ ] Freeze benchmark, verifier, agent, image, protocol, and manifest.
- [ ] Run approximately 30–40 quality-approved tasks, balanced across the four cells
  and crypto families, with at least three runs per task and up to five if budget allows.
- [ ] Validate every batch; preserve raw trajectories and classify infrastructure
  failures separately.

## Phase 6 — Analysis

- [ ] Implement model-first hierarchical analysis with the task family as cluster.
- [ ] Use the preregistered GEE or equivalent cluster-robust model, confidence
  intervals, effect sizes, and multiplicity control.
- [ ] Produce trace-derived metrics and figures without treating actions as samples.
- [ ] Blind and adjudicate qualitative trajectory coding.
- [ ] Run robustness checks for difficulty, timeout, tool errors, repetition, and
  verifier artifacts.

## Phase 7 — Paper and release

- [ ] Generate every table and figure from raw-data hashes through the analysis code.
- [ ] Complete peer, red-team, safety, and reproducibility audits.
- [ ] Write results only from measured data; distinguish data, interpretation, and
  non-conclusions.
- [ ] Release only safe task specifications, code, metadata, and sanitized traces;
  never release credentials, host paths, unsafe target capability, or private logs.

The legacy generic stopping-study documents and pilot results remain available for
audit history. They are not silently reinterpreted as evidence for this crypto study.
