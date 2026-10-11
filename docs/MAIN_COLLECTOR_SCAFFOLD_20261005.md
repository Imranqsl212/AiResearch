# Excluded main trace recorder scaffold — 5 October 2026

[`experiments/main_collector.py`](../experiments/main_collector.py) is a
**scripted fixture recorder** for one slot in an ungated proposed main plan. It
does not connect to a provider, run an evaluator, or emit eligible main data.
Its receipts set `phase=pilot`, `eligible_for_main_analysis=false`,
`main_dispatch_allowed=false`, and `model_calls=0`. The main gate remains closed.

The recorder verifies the selected slot's task and proof hashes against the
plan's complete source inventory. It copies exact source bytes, records a plan
snapshot, checks the supplied model digest and inference configuration against
the plan, and refuses a request whose model, seed, or provider options differ.
Each scripted request is written before its fixture response, and both byte
sequences are retained with SHA-256 hashes. The offline verifier rehashes the
archive and reconstructs actions from the saved responses. Files are write-once
with mode `0600`, and the slot directory is mode `0700`.

One response consumes one decision, including `inspect`, `terminate`, and an
explicit claim. Submissions are counted separately. A scripted `PASS` does not
close the episode; only a voluntary stop, timeout, or six decisions do. A
voluntary stop at decision six is marked as a budget-edge stop rather than an
early stop. A malformed response or interrupted request remains in the slot
archive and requires an explicit invalidation receipt; the slot ledger says
`replacement_count=0`.

`python3 -m unittest tests.test_main_collector -v` exercises seven scripted cases,
including continued decisions after `PASS`, budget-edge stopping, malformed
response preservation, model/config mismatch, source drift, and archive tamper
detection. These are contract tests, not research observations.

## Missing for a live main collector

- A reviewed live adapter must prove that request archival completes *before*
  each network dispatch and that response bytes are captured directly afterward.
  The scaffold only enforces that order for caller-provided fixture bytes.
- The supplied model digest is checked against the plan but is not queried from
  a live provider. The source map is checked against local bytes, but a final
  frozen Git commit, runtime/container identity, and immutable source release
  still need their own verification.
- Agent actions are parsed from scripted response bytes; task-specific candidate
  shape, independent oracle, proof identity, feedback channel, and R1 retrieval
  delivery are not executed or validated here. Scripted verdict labels are
  explicitly marked unverified.
- C5 agent-generated pre-verdict onset capture, transcript cloning, concealed
  randomized branch assignment, three-decision branch parity, and a complete
  precursor/nonreach ledger have a separate
  [fixture-only scaffold](MAIN_C5_FORK_SCAFFOLD_20261005.md). Live integration
  and independent oracle verification are still unimplemented.
- Human admission, retrieval source review, schedule freeze, privacy review,
  blinded coding, and evidence-backed main release receipts remain required.

No fixture output from this module can be promoted into the main analysis.
