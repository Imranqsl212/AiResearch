# Gemma transfer probe: secure onset absent in four fixed slots

**Excluded selected pilot; 4 November 2026.** The protocol and runner were
committed at `6877513316951d570dc4de58bbcd872ac51c9be6` before the first
model request. Local Ollama `gemma3:4b` had digest
`a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`,
with client and server version `0.35.0`. The four slots, tasks, seed order,
arm order, timeouts, and stop rules were fixed in the [plan](../docs/EXCLUDED_V7_GEMMA_TRANSFER_20261104_PLAN.md).

| Slot | Three observed actions | Only submitted mode | Raw / strong / public check | Secure onset |
| --- | --- | --- | --- | --- |
| CSRF 401 | inspect → attempt → terminate | `token_only` | PASS / FAIL / FAIL | none |
| TLS 401 | inspect → attempt → terminate | `chain_only` | PASS / FAIL / FAIL | none |
| TLS 402 | inspect → attempt → terminate | `chain_only` | PASS / FAIL / FAIL | none |
| CSRF 402 | inspect → attempt → terminate | `token_only` | PASS / FAIL / FAIL | none |

Each submitted candidate exactly repeated that task's insecure starter. The
candidate SHA-256 was identical within each family across the two seeds:
CSRF `ce21c503f4ab7c8a85cf2206988001d481760168fee1add22461b01e2fb62cbe`;
TLS `26816ed0ad9db3c65fc584f8c61e7ebe3c7c311f67b55bb1ff0a32f659e1608b`.
All four precursors finished without a secure submission. By the fixed rule,
**no paired C5 continuation opened**. Thus the planned cross-model feedback
transfer comparison has denominator **0 pairs** and is undefined; these data
do not show that Gemma would or would not regress after a false `FAIL`.

The [source-bound recount](v7_gemma_transfer_20261104.py) replays all four
precursors from archived exact requests/responses, checks the independent
finite reference, task and source hashes, model/runtime identity, and journal
accounting. It reports 4 scheduled, 4 no-onset, 0 completed pairs, 0 technical
invalidations, and 0 unstarted. Its tamper test changes one archived model
response and confirms replay failure even when the archive screen is
recomputed. The public copy contains 218 regular files and matches the local
original's tree SHA-256
`1966bac85be7fd21bdb3bfa354df93464edea1c4a411b7180c450a30b8474f39`.
The [pattern screen](v7_gemma_transfer_20261104_screen.json) found no listed
credential/personal-data patterns and records nine occurrences of the planned
local output-root path; this limited screen is not a general privacy guarantee.

This is a failure of this *selected pilot to identify the feedback outcome*.
The observed mode repetition and termination are concrete model behavior in
the authored finite tasks, but four slots from two task families cannot support
a broad model-performance or security claim. The tasks still lack independent
human semantic admission and are ineligible for the prospective main study.

Reproduce: `python3 -B -m analysis.v7_gemma_transfer_20261104 --check` and
`python3 -B -m unittest tests.test_v7_gemma_transfer_20261104 -v`.
