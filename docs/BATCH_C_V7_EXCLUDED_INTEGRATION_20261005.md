# Batch-C v7 excluded integration check

**5 October 2026 — engineering only.** The eight `7.0.0` batch-C family keys
dispatch to `benchmark.finite_batch_c_v7`; the corresponding `6.0.0` keys
still dispatch to v6. The v7 public task uses the finite-options prompt and
the exact public `candidate_language` contract. The collector records the
v7 evaluator and independent reference SHA-256 hashes in both source
snapshots. The analyzer requires identical snapshots, checks the complete
excluded implementation inventory against current bytes, then recomputes
the proof and every candidate receipt. The saved task and proof bytes are
also individually hashed in each episode manifest.

`tests/test_v7_excluded_integration.py` uses a callback that returns fixed
JSON in place of a provider. It collects and replays each of the eight C1
families: all reach a secure, gate-passing candidate. It also checks a C3
unrepairable case without witness disclosure, a C4 case with the authored
contradiction disclosed, and a C5 secure-oracle result rejected by the gate.
Negative cases reject missing, drifted, and self-consistently forged v7
source hashes. The main collector remains blocked. No model was called and
none of these temporary runs is a scientific observation or main episode.

Run the focused check with:

```sh
python3 -B -m unittest tests.test_v7_excluded_integration -v
```

**Still required before any admission:** two independent family security
reviews and adjudication; a decision about whether full required-output
conformance, including legitimate-request availability, is the intended
security construct; review of the eight authored world assumptions and
public mode disclosure; R1 source/corpus alignment and review; a prospective
freeze and main schedule bound to v7; a real-model dry run and complete
collector preflight. V6 pilot outcomes cannot be transferred to v7.
