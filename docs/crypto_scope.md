# Cryptographic scope

## Chosen domain

The first empirical domain is application-level cryptographic misuse involving
authenticated encryption. Tasks use standard library APIs; they do not ask an agent
to invent AES, GCM, or another primitive.

The initial security invariants are:

| Family | Invariant | Typical failure |
| --- | --- | --- |
| `aead` | Encryption provides confidentiality and ciphertext integrity. | Encryption-only API or ignored authentication failure. |
| `nonce` | A nonce is unique for each encryption under a key. | Reused, predictable, or incorrectly persisted nonce. |
| `key-management` | Keys are obtained through the permitted interface and are not hardcoded. | Embedded key, unsafe fallback, or incorrect key lifecycle. |

The active benchmark is a controlled repair benchmark, not a vulnerability scanner and
not a live bug-bounty environment. A task may contain an intentionally flawed local
snippet, but the target and verifier are disposable and offline.

## What the agent receives

The agent receives a local code workspace, a bounded tool contract, and checker
feedback. It does not receive the condition label, hidden oracle, reference solution,
verifier implementation, image build context, host files, credentials, or private
chain-of-thought fields.

The checker feedback is an experimental factor:

- diagnostic: identifies the violated invariant sufficiently to test a new hypothesis;
- weak: truthful evidence that the current attempt failed but does not fully identify
  the repair;
- infrastructure error: a separate control and never crypto evidence.

Feedback must never invent a false security result. A distractor is a plausible but
irrelevant repair path, not a fake vulnerability claim.

## What counts as adaptation

- parameter change: values or API arguments change while the same design remains;
- implementation change: code structure changes within the same design;
- hypothesis change: the agent tests a different explanation of the cryptographic flaw;
- strategy change: the agent switches security design, such as encryption-only to AEAD
  or hardcoded-key use to an approved key interface;
- repetition: the same hypothesis and security design are retried with no
  outcome-changing change.

Different syntax is not automatically a strategy change.

## Safety boundary

All execution is local. No public IP, third-party service, real credential, or
production key is allowed. The verifier runs outside the agent-visible workspace and
counts success only when the independent cryptographic invariants and regression tests
pass.

## Extensions, not current scope

Password hashing, digital signatures, certificate validation, OpenSSL configuration,
and key exchange are future task families. They should not be mixed into the first
confirmatory analysis because they introduce different APIs, threat models, and
security oracles.
