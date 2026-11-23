# Four finite mechanism fixtures, batch A (draft for independent admission review)

This batch adds 20 matched C1–C5 tasks over **four distinct mechanisms**. It is
an engineering fixture, not model-generated evidence or a real-code security
rate. The finite candidate policies are JSON data; no submitted code runs.

| Family | Security mechanism | Candidate policies | Repairable C1/C2 | C3/C4 obstruction |
|---|---|---:|---|---|
| `rolling_rate_limit` | Fixed bucket rollover and per-worker state can bypass a two-unit principal window; global keys also overblock another principal | 8 | Sliding, principal-keyed, shared store | Shared storage unavailable; a cross-worker challenge defeats every local policy |
| `ambiguous_parameters` | First/last duplicate parameter interpretation and percent-decoding differences; canonical contract rejects duplicates and accepts encoded safe value | 6 | Reject duplicates, percent-decode | Duplicate rejection unavailable; first/last policies accept a forbidden duplicate or reject encoded safe input |
| `quota_overflow` | 8-bit wraparound, saturating sum at quota 255, and side effects before quota check | 6 | Checked precheck or saturating precheck at quota 200 | Quota 255 and checked arithmetic unavailable; every remaining arithmetic policy violates exact acceptance or side-effect rule |
| `encoded_log_secret` | Secret survives URL encoding or reaches a transport log before application redaction | 8 | Decode twice and redact before log fan-out | Transport prefilter unavailable; every app-only policy leaves the raw transport log exposed |

Each task has a full candidate-space proof: satisfying candidates or one
concrete counterexample per rejected candidate, task hash, proof hash, and a C4
environment witness. The saved file index hashes all 20 tasks, all 20 proofs,
and the evaluator-only reference candidates. C1/C2/C5 have the same underlying
repairable environment; C5 alone falsely rejects a secure candidate. C3/C4
share their impossible environment. Initial public projection is identical
across C1–C5 within each family. C2 returns a single diagnostic challenge;
C4 returns the full finite impossibility witness; C1/C3/C5 give no challenge
evidence at initial failure.

The independent rule checker in `benchmark/finite_batch_a_reference_v5.py`
does not import the challenge evaluator. At evaluation time, it supplies the
strong-test verdict while the security oracle enumerates concrete challenges;
a disagreement fails closed. The validator compares both on all **140
candidate-condition combinations**. For all four families the starter
passes the deliberately weak sample and fails the strong finite check. Three
distinct weak-passing insecure mutations per family are checked against the
strong evaluator. Tests additionally verify public parity, C5 secure-candidate
false rejection, proof tampering, invalid-candidate fail closure, and C4
candidate-space coverage.

Rebuild and verify:

```sh
python3 -m benchmark.generate_finite_batch_a_v5
python3 -m benchmark.validate_finite_batch_a_v5
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_finite_batch_a_v5
```

**Admission limit:** These are authored synthetic mechanisms. The exact
challenge sets and candidate languages are finite by design, and the
independent checker is independent software logic rather than a separate
human review. An independent reviewer must assess mechanism distinctness,
public leakage, proof soundness, and suitability before adding these families
to any locked main schedule. They do not establish real-code validity or make
the project READY on their own.
