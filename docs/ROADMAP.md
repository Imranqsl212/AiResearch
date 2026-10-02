# Roadmap: When Secure-Code Repair Fails

**Scope:** how a local provider-backed AI agent responds to independently verified
crypto/web security failures, and how feedback and retrieved knowledge affect that
response.
**Current state:** executable benchmark v0.5.0, 20 security families, approved Docker
image, excluded Ollama smoke traces, a frozen retrieval corpus, and a fail-closed
factorial runner exist; no confirmatory pilot or main experiment has been executed.

## Phase 0 — Scope and literature freeze

- [x] Deep-read the three mentor-provided papers and the closest feedback,
  self-correction, RAG, vulnerability-repair, and tool-reflection sources.
- [x] Refine the gap to strategy transitions, RAG-versus-feedback separation,
  infeasibility, stopping, and false success.
- [x] Draft the Introduction and five-question source review.
- [ ] Mentor review and final preregistration/citation freeze.

## Phase 1 — Benchmark construction

- [x] Generate 80 executable target definitions: 20 families × RD/UD/RW/UW.
- [x] Add schema, static quality gate, family balance, and deterministic oracle checks.
- [x] Implement a local executable Go AEAD target and evaluator-only verifier receipts.
- [x] Extend executable reference verification to nonce and key-management families.
- [x] Add a 20-document, leakage-reviewed, hashed security-guidance retrieval corpus.
- [x] Add deterministic `RAG relevant/off` treatment arms without changing target
  semantics.
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
- [x] Run excluded smoke tests and verify complete traces; no smoke is treated as
  research data.

## Phase 4 — Pilot

- [ ] Run the predeclared 24-arm pilot: three families × RD/UD/RW/UW × RAG on/off.
- [ ] Check task distinguishability, verifier validity, feedback leakage, logging,
  strategy labels, and confounding before any main run.
- [ ] Record every pilot change as a protocol amendment; do not silently alter tasks.

## Phase 5 — Main experiment

- [ ] Freeze benchmark, verifier, retrieval corpus, agent, image, protocol, and
  manifest.
- [ ] Use pilot timing/variance and a pre-data power simulation to choose the main
  family count. The full upper bound is 160 treatment arms (80 targets × RAG on/off)
  and 480 runs at three repeats; do not launch it automatically on the M1 laptop.
- [ ] Validate every batch; preserve raw trajectories and classify infrastructure
  failures separately.

## Phase 6 — Analysis

- [ ] Implement the preregistered factorial GEE with family clusters, small-sample
  correction, blocked permutation sensitivity analysis, and documented mixed-model
  fallback.
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
