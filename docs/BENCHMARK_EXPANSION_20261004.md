# Controlled-family expansion plan — 4 October 2026

## Present evidence and count discipline

The master research specification calls for **at least 20 matched task families × four core conditions × five repetitions**, approximately 400 core episodes; C5 is an additional mismatch arm. Authorization v1, path boundary v2 and transaction replay v3 are existing finite mechanisms. Counter race v4 adds a fourth **offline engineered** mechanism with saved proofs and independent checker comparisons. These four are not four independently reviewed, main-admitted families. The legacy catalog's nominal family count and the separate real-code external-validity tier cannot be added to this controlled-family count without the same prospective review and condition matching. At least **16 more distinct controlled mechanisms** remain to reach the requested minimum, followed by admission review of all 20.

## Proposed mechanism queue

These are candidates for design, **not implemented or validated families**. A proposal may be rejected or merged with another if its threat model or failure mechanism is not sufficiently distinct. For each proposed row, the review must specify the exact candidate language, trust boundary, security invariant, weak/strong tests, independent oracle, C3/C4 impossibility proof, C5 false-failure onset, and at least two meaningful insecure mutations before any data collection.

| # | Candidate mechanism | Independent oracle or reference direction | Key distinctness question |
| --- | --- | --- | --- |
| 1 | SQL parameter binding | Disposable SQL engine and an independently written query/result checker over payload classes | Is this query construction rather than an authorization policy? |
| 2 | HTML output context encoding | Browser/DOM based safety probes across text, attribute and script contexts | Does the fixture test actual parsing instead of string matching? |
| 3 | Shell command argument separation | Isolated subprocess harness with metacharacter and quoting probes | Does it test process invocation rather than generic escaping? |
| 4 | SSRF destination validation | Local DNS/HTTP simulation with address-class and rebinding traces | Is it distinct from static path-boundary ambiguity? |
| 5 | Deserialization type control | Isolated parser with allowlist and gadget-like inert side effects | Can safety be observed without executing unsafe real payloads? |
| 6 | CSRF request binding | Finite session/token/origin state machine, separately checked | Is it distinct from the existing authorization decision table? |
| 7 | Session-token entropy | Seeded generator class with exhaustive collisions in a small domain, plus external RNG probes | Is the finite entropy claim meaningful and precisely scoped? |
| 8 | AEAD nonce uniqueness | Encryption-call traces under keys, restarts and parallel allocation | Is this different from transaction replay's duplicate-request state? |
| 9 | AEAD tag verification | Isolated cryptographic API with altered ciphertext/tag challenge corpus | Can the oracle derive authenticity independently of candidate checks? |
| 10 | KDF parameter and salt handling | Known-answer derivations plus work-factor and uniqueness probes | Are performance and misuse thresholds predeclared? |
| 11 | Digital signature verification | Independent signature library with malformed-key and algorithm-confusion cases | Is a secure reference available without oracle sharing candidate code? |
| 12 | Secret redaction in logs | Separate sink capture and taint-labeled source corpus | Does the oracle measure information release rather than keyword absence? |
| 13 | TLS verification configuration | Local test CA, wrong-host and invalid-chain endpoints | Can the fixture avoid external network and clock drift? |
| 14 | File-permission creation race | Isolated filesystem harness with umask and attacker-observable windows | Is it distinct from the path-resolution family? |
| 15 | Key rotation and stale-key acceptance | Bounded cryptographic key lifecycle with independent verifier | Does it test lifecycle behavior, not mere signature verification? |
| 16 | Multi-tenant cache isolation | Paired tenant traces with independent cache-observation checker | Is the shared-state leak distinct from simple role authorization? |

The queue deliberately spans web, cryptography, concurrency and secure software engineering. It is a **work plan**, not a claim that these sixteen will all pass review. Any rejected mechanism must be replaced by another genuinely distinct, proof-backed family before the minimum is met.

## Family admission gate

1. Freeze a concrete threat model and allowed action grammar. C3/C4 must be genuinely impossible **under that grammar**, demonstrated by a checker or independent environmental constraint; setting a reachability flag is insufficient. State the real-world escape routes excluded by the grammar.
2. Produce C1–C5 tasks with matched public task cards and action/time budgets. Derive truth independently of the condition label; verify that C2 evidence is truthful, C4 evidence is a checked impossibility witness, and C5 rejection starts only after an oracle-secure submission.
3. Keep raw weak tests, stronger adversarial tests, security oracle and benchmark gate as separate outputs. Cross-check every finite candidate when tractable, and compare against a second implementation or actual isolated runtime. Include secure references and distinct insecure mutations, reporting mutation sensitivity by family.
4. Hash and index task, proof, reference, prompt and evaluator artifacts. Review agent-facing projections for hidden labels, answers and proof leakage. Use an independent reviewer to accept or reject the threat model and domain distinctness before prescheduling main slots.
5. Run excluded live pilots on the exact adapter and runtime. Record every invalid action, timeout, request and provenance hash. Validate the analysis path and freeze the admitted set before main collection. A pilot can repair engineering faults but cannot become a main observation.

Only after all admitted families and other gates pass should the root manifest be considered for READY. A narrower study is possible only after explicitly changing the research scope and claims **before** prospective collection; it must not silently present four fixtures as the requested twenty-family result.
