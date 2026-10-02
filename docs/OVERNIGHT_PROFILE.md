# Exploratory Overnight Profile

This profile is a resource-bounded feasibility study for the local `qwen3:4b`
agent on an 8 GB Apple-silicon laptop. It is not a replacement for the frozen
confirmatory repeated-run design.

## Frozen design

- Pilot: `aead`, with all four `RD/UD/RW/UW` conditions crossed with retrieval
  `off/relevant` (8 arms, one run each).
- Main: `key-derivation`, `nonce`, `weak-randomness`, `sqli`, and `xss`, each
  with the same complete 4 x 2 design (40 arms, one run each).
- Pilot and main base tasks are disjoint.
- Temperature and seed remain fixed at `0` and `7`.
- Agent execution remains local through Ollama; candidate code remains inside
  the independently checked no-network Docker boundary.
- Maximum steps are frozen at launch (default: 6); success counts only when the
  independent executable verifier confirms it.
- The Ollama request timeout is 600 seconds and the episode timeout is 1800
  seconds by default. Both values are frozen in the new run configuration.

## Gate sequence

The launcher fails closed in this order: Ollama/catalog/RAG/profile validation,
Docker image mapping, the complete safety suite, one excluded smoke run, eight
pilot runs, pilot artifact integrity, and only then the 40-arm main run.

## Interpretation limits

There is one observation per arm and only five main task families. Results can
support feasibility checks, descriptive comparisons, trajectory examples, and
variance estimates for planning the full experiment. They must not be reported
as a preregistered confirmatory test or as definitive GEE evidence. Repeated-run
GEE analysis remains blocked until additional independently scheduled repeats
are collected.

The launcher records these deviations in its nightly report and gives the run
a separate experiment identifier beginning with `rag-overnight-v2`.

The earlier `rag-overnight-v1` pilot remains in the historical accounting
snapshot. Its `INFRASTRUCTURE_ABORT` records the original 300-second Ollama
timeout. Those pilot and smoke attempts are engineering evidence only; the
v2 pilot is collected under the new timeout and separately identified.

At startup and after each phase, `experiments.accounting` creates a local
snapshot of all available manifests, logs, receipts, results, and nightly
reports. Every run has its hashes and integrity status. The snapshot stays
local until raw experiment metadata receives publication review.

To start or inspect the current profile:

```sh
PYTHONDONTWRITEBYTECODE=1 caffeinate -dimsu python3 -B -m experiments.run_rag_overnight_profile --run-main
PYTHONDONTWRITEBYTECODE=1 python3 -B -m experiments.accounting
```
