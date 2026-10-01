# Project status: cryptographic repair study

**As of:** 2026-09-30
**Active project:** *When Secure-Code Repair Fails*
**Scope:** observable adaptation and stopping after cryptographic misuse feedback.

## Executive summary

The project has been narrowed from broad cybersecurity-agent behavior to a safe local
study of cryptographic code repair. The active benchmark is version 0.3.0 with three
families—AEAD, nonce handling, and key management—and four matched cells per family:
repairable/diagnostic (RD), unavailable/diagnostic (UD), repairable/weak truthful (RW),
and unavailable/weak truthful (UW).

The Docker Desktop safety gate and declarative benchmark checks pass. An executable
AEAD/nonce/key-management target layer, a local Ollama adapter, and excluded smoke
episodes now exist. No pilot or main experiment has run, and excluded smoke episodes
are not empirical study data.

## Implemented

- crypto-specific task generator, schema, 12 development manifests, and quality gate;
- independent declarative oracle/receipt layer;
- crypto scope, protocol, research-gap, preregistration, roadmap, and manuscript;
- Docker Desktop LinuxKit isolation policy, immutable approved local image, and runtime
  safety checks;
- provider-neutral agent and observable trajectory contracts;
- loopback-only Ollama adapter for `qwen3:4b`, with tool allow-list and bounded output;
- executable Go AES-GCM and nonce-family targets plus key-management target;
- independent nonce/integrity/key-management verifiers with immutable receipts;
- approved immutable Docker crypto image with local self-checks and full safety receipt;
- bounded Ollama protocol recovery for prose/tool-call failures;
- manifest, attempt-ledger, raw-archive, and analysis infrastructure from the earlier
  stopping-study scaffold.

## Not implemented

- provider-backed agent integration is implemented for local Ollama, and an excluded
  smoke agent has produced an observable repair attempt; reliable verifier-confirmed
  repair is not established;
- executable Docker image is safety-approved, but the full 12-task Docker-backed
  target mapping and hidden-verifier deployment are not implemented;
- smoke acceptance for pilot is still blocked by invalid submissions/inference timeout;
- crypto pilot;
- main 30–40-task experiment;
- real-data GEE/model-first analysis and paper results.

## Scientific design

The primary question is whether post-failure changes are outcome-changing crypto
strategy changes or surface-level persistence. The inferential cluster is the task
family; runs are nested, and actions are not independent observations. Success is
verifier-confirmed only. Unsupported success claims, voluntary stops, budget stops,
timeouts, tool errors, infrastructure failures, and invalid tasks remain distinct.

## Risks still requiring resolution

The main risks are API-memorization confounding, unequal executable-task difficulty,
feedback leakage, verifier false positives/negatives, provider stochasticity, limited
task-family clusters, and budget-driven stopping. The protocol addresses these with
matched cells, hidden labels, independent receipts, frozen configs, explicit terminal
classes, alternate-route validation, and cluster-aware analysis; runtime validation is
still required.

## Immediate next steps

1. Finish executable task adapters for all 12 matched family/cell manifests and
   validate alternate repair/unavailable paths.
2. Define and freeze the smoke acceptance rule, then obtain a non-infrastructure
   smoke receipt under the final adapter configuration.
3. Freeze provider/model/agent/image/protocol versions and final manifest.
4. Run the pilot, inspect integrity without changing the protocol silently.
5. Only after pilot approval, run the main experiment and model-first analysis.

Legacy generic stopping-study reports and synthetic traces remain retained for audit and
are not evidence for this crypto study.
