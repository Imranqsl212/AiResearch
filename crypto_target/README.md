# Executable local crypto target

This fixture is the first executable implementation of the narrowed study. It uses
Go's standard `crypto/aes` and `cipher.NewGCM` packages and never contacts a network.
The initial solution intentionally reuses a nonce, so it is not a secure reference
implementation. The independent verifier checks nonce uniqueness, authenticated
decryption, tamper rejection, and associated-data rejection.

The agent-visible workspace contains `solution.go` and a task card. The generated
verifier test is evaluator-only and is copied into a temporary workspace. The agent
cannot read or modify it. This is a local executable fixture; Docker image integration
and the final per-task receipt channel remain separate launch gates.

Run the verifier without an agent:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m crypto_target.verifier --workspace crypto_target/templates/aead_nonce_reuse
```

The initial fixture is expected to fail because it reuses a nonce. A corrected
candidate must generate a fresh random nonce for every encryption and serialize the
nonce with the ciphertext so decryption can recover it.
