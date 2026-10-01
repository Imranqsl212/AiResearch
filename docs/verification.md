# Independent cryptographic verification

**Active verifier:** `crypto_four_cell_receipt_v1`
**Version:** `0.3.0`
**Implementation:** [benchmark/validators](../benchmark/validators)

An agent statement never establishes that code is secure. The evaluator runs an
independent checker against the actual local artifact and emits a receipt containing
task/version identifiers, invariant results, evidence classes, state hash, and
terminal class.

## Required checks

| Family | Independent assertion |
| --- | --- |
| `aead` | ciphertext integrity failures are rejected and valid authenticated decryptions succeed |
| `nonce` | nonce uniqueness is preserved for repeated encryption under the same key |
| `key-management` | key material is not hardcoded or silently replaced by an unsafe fallback |

Every success check must include positive and negative cases, regression behavior,
and a test that the agent cannot pass by changing only the test or verifier. A
repairable task must be checked through at least two permitted routes where the
manifest claims alternatives; an unavailable task must be checked by an independent
alternate-route search, not only by replaying one failed path.

## Receipt rules

The registry fails closed on an unknown verifier ID or version. A terminal success
claim without a passing receipt is `UNSUPPORTED_SUCCESS`. A failing checker, missing
receipt, nondeterministic result, or discovered reachable route in `UD`/`UW` yields
`INVALID_TASK` or `INFRASTRUCTURE_FAILURE`, never an agent-failure label.

```text
task + local artifact
        ↓
independent crypto checker
        ↓
hash-linked evaluator receipt
        ↓
trajectory terminal record
```

The verifier process and receipt store must be outside the agent-visible workspace.
The agent cannot read or modify the verifier, oracle, image build context, host
filesystem, credentials, clock, or raw archive.

## Current implementation boundary

The static four-cell validator checks declarative reference receipts. It does **not**
yet prove executable Docker-target behavior. The provider-backed agent, executable
crypto target, smoke test, pilot, and main study remain **NOT IMPLEMENTED**. No
empirical result may be reported until these gates pass.
