# Literature review: AI agents repairing cryptographic misuse

## Scope and status

This review narrows the project from general cyber-agent persistence to a specific,
safe question: how an AI coding agent responds after an independent checker rejects
cryptographic code. It distinguishes established findings from the proposed
interpretation. The repository's older general-agent matrix remains as background
provenance; the active study uses only sources relevant to crypto invariants,
tool-using revision, independent verification, and stopping.

## 1. Cryptographic invariants are testable, not stylistic

NIST SP 800-38D defines GCM and GMAC and provides the normative context for
authenticated encryption. RFC 5116 specifies an interface for authenticated-encryption
algorithms, including the relationship between plaintext, associated data, nonce,
ciphertext, and authentication tag. RFC 8446 shows how authenticated encryption is
used in a real protocol setting. OWASP's Cryptographic Storage Cheat Sheet translates
common implementation concerns into engineering guidance, including key protection
and avoiding homemade cryptography.

These sources establish the security properties that a verifier can test. They do not
study agent adaptation. The benchmark therefore treats crypto correctness as an
external oracle: a passing implementation must satisfy invariant-specific positive
and negative tests, rather than merely resemble a recommended code pattern.

## 2. Tool use and iterative correction

ReAct established an interleaved action-observation pattern for language-model agents.
Reflexion and Self-Refine show that textual feedback can improve later attempts without
weight updates. These works motivate collecting ordered trajectories and delivering
checker feedback between attempts.

Their primary outcomes are task performance or output quality. They do not, by
themselves, distinguish a parameter mutation from a change in security design, or
define when a stop is supported by evidence. The present protocol adds that
distinction in a narrow cryptographic setting.

## 3. Recovery, abstention, and terminal verification

Recent agent evaluations study recovery from failed plans, act-versus-abstain choices,
and state-based completion checks. The methodological lesson is direct: a benchmark
must include both feasible and infeasible cases, and a natural-language completion
claim is not ground truth.

The crypto benchmark applies this lesson through four matched cells. Repairability and
feedback diagnosticity are separate factors. A verifier outside the agent workspace
determines success. Voluntary stop, timeout, budget stop, tool error, and unsupported
success are separate terminal classes.

## 4. Crypto misuse research and the remaining behavioral question

Cryptographic API-misuse research and vulnerability datasets typically focus on
detecting a bad pattern, ranking findings, or producing a corrected implementation.
They answer whether a vulnerability is present or whether a patch passes a test. They
normally do not expose an agent to a sequence of controlled checker outcomes and then
measure whether it retires a hypothesis, changes a design, or keeps trying.

That distinction matters because more edits do not necessarily mean more adaptation.
For example, changing a nonce value may preserve the same flawed encryption-only
design; replacing the construction with authenticated encryption is a different
strategy. The benchmark's codebook and independent receipt are intended to make this
difference observable.

## 5. Research gap and contribution

The broad claim—nobody has studied agents after failure—is not supported. Self-
correction, recovery, abstention, process metrics, and executable security benchmarks
are existing lines of work. The narrower gap is methodological:

- existing crypto guidance defines what secure code should satisfy;
- existing agent work measures revision or eventual success;
- existing recovery work compares feasible and infeasible goals;
- the proposed study combines these into matched crypto tasks with a trace-level
  taxonomy of adaptation and stopping, plus verifier-backed unsupported-success
  measurement.

This contribution remains conditional. If behavior is fully explained by API recall,
feedback wording, task difficulty, timeout, or checker artifacts, the study should
report that result rather than claim evidence-sensitive strategy adaptation.

## 6. Sources

- [NIST SP 800-38D](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38d.pdf)
- [RFC 5116](https://www.rfc-editor.org/rfc/rfc5116)
- [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [ReAct](https://arxiv.org/abs/2210.03629)
- [Reflexion](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html)
- [Self-Refine](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html)

The focused source matrix is [crypto_literature_matrix.csv](crypto_literature_matrix.csv).
The older broad matrix remains a research aid and must be checked against primary
sources before any publication claim. No empirical result is inferred from this review.
