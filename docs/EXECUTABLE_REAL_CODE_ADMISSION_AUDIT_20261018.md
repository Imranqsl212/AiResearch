# Executable-code external-validity audit — 18 October 2026

**Disposition: no executable-code family is admitted to the prospective main
study.** The repository contains one historical 80-row executable catalog and
two separate, stronger Docker calibration fixtures. These are different
artifacts and must not be pooled with the 20 finite-policy families or
presented as a prospective real-code effect estimate.

| Artifact | What actually runs and is checked | Evidence | Admission |
| --- | --- | --- | --- |
| [Legacy executable catalog](../benchmark/tasks/executable/catalog.jsonl) | 20 Python-source families × RD/UD/RW/UW = 80 rows (48 crypto, 32 web). Actual episodes use the pinned Docker candidate runtime; most family checks are one or two fixed `assert` examples. | Balanced catalog and scripted vulnerable/secure reference files; no independently held-out security oracle for the 80 rows. | **Not admitted** |
| [SQLite injection v3](../benchmark/real_code_sqli_notes.md) | One local in-memory SQLite equality lookup. Host computes expected answers with parameter binding; candidate executes in Docker. | Eight cases per profile, five source profiles; two insecure mutations pass weak tests and fail strong tests. Saved calibration says `calibration_passed=true`. | Calibration only; no agent-written repair |
| [Command injection](../benchmark/real_code_command_injection_notes.md) | One local file-command interface. Host checks expected content and a marker side effect after Docker execution. | Eight cases per profile, four source profiles; two insecure mutations pass weak tests and fail strong tests. Saved calibration says `calibration_passed=true`. | Calibration only; no agent-written repair |

## Decisive defects in the legacy 80-row tier

1. **All 40 `UD/UW` cells use a post-verifier veto, not a removed resource.**
   [`sandbox/docker_candidate.py`](../sandbox/docker_candidate.py) sends only
   `domain`, `family`, and `source` into the container. It then sets
   `condition_reachable=false` for `UD/UW` and changes an actual `PASS` to a
   final failure. The [catalog validator](../benchmark/validate_executable_catalog.py)
   likewise rewrites successful host verifier receipts to
   `condition_unreachable` for these cells. This recreates the hidden-veto
   measurement problem; it cannot measure recognition of genuine
   unavailability. The version `0.5.0` catalog should remain historical.
2. **The historical AEAD tamper assertion is swallowed.** The checked-in
   [Docker runtime](../sandbox/images/candidate_runtime.py) decrypts a modified
   ciphertext, raises `AssertionError` if decryption returns, then catches
   `Exception` around both operations. An always-decrypting counterfeit passes
   this test. The [regression test](../tests/test_candidate_runtime_v2.py)
   reproduces that false acceptance without Docker or a model call.
3. **The historical secret-leakage “secure” reference leaves the secret in
   output.** Its replacement produces `secret=<redacted>top-secret`. The old
   checker looks only for the exact substring `secret=top-secret`, so it
   accepts this disclosure. The same offline regression verifies the leak.
4. **Several family labels exceed the implemented challenge.** For example,
   the legacy SQLi “secure” reference returns the literal string
   `"parameterized"` without running a SQL query, and the command-injection
   reference rejects only selected shell separator substrings. The fixed
   snippets can demonstrate responses to those examples, not general SQL or
   shell safety. The separate SQLite and command fixtures above provide the
   stronger host-owned evidence for those two mechanisms only.

The catalog's structural validator can still say `passed=true` after checking
balance and expected reference outcomes; its `UD/UW` result is produced by the
same post-verifier override. That status is **not** scientific admission.
The host-side catalog validation also imports candidate reference code in a
host subprocess for 17 families; it is not an isolation proof for arbitrary
model submissions. The actual legacy episode path uses Docker but retains
the finite test and veto limitations above.

## Versioned engineering repair, not a new result

The original pinned runtime source and Dockerfile are preserved. A separate
[candidate v2 runtime](../sandbox/images/candidate_runtime_v2.py),
[v2 Dockerfile](../sandbox/images/candidate_runtime_v2.Dockerfile), and
[v2 secret reference](../crypto_target/templates_extended/secret-leakage/secure_reference_v2.py)
fix the two demonstrated checker defects. Five offline regression tests show
that v1 accepts the always-decrypting counterfeit, v2 rejects it, v2 accepts a
tamper-rejecting double, v2 rejects the leaking old reference, and the new
reference removes the secret value. These offline tests alone do not establish
Docker isolation or task admission. The other narrow family checks and all
post-verifier `UD/UW` vetoes remain unrepaired in the historical catalog.

```sh
python3 -B -m unittest tests.test_candidate_runtime_v2 -v
python3 -B -m unittest tests.test_real_code_sqli tests.test_real_code_command_injection -q
```

On 18 October the commands passed 5 and 6 offline tests, respectively. The
saved SQLite and command calibration JSON each matches its current suite
manifest and SHA-256, each source profile and runtime-driver hash, eight
case records per profile, and `COMPLETED`/container-removed receipts. This is
a consistency check of saved local artifacts, not a fresh Docker calibration
or independent human validation.

## Candidate image containment completed on 18 October

The v2 source was built offline as
`local/candidate-runtime@sha256:fe4daf243d6575ddcfdaac4a6143001ed89c4d1bf31e961770c0a2af84fd3d5a`
from the locally verified v1 base. The separately versioned
[candidate lock](../sandbox/images/candidate_images_v2.json) pins that digest.
The [v2 preapproval receipt](../sandbox/safety_checks/candidate_result_v2.json)
records **11/11 passing checks**, including blocked external networking,
absent host mounts and credentials, process/resource limits, cleanup, retained
logs, reproducible state, and the candidate runtime probe under the local
Docker Desktop LinuxKit VM. `experiment_permitted=false` and
`approval_scope=CANDIDATE_ONLY_NOT_APPROVED` remain explicit. The ordinary
episode runner rejects both candidate locks; its regression test passes.
The receipt is bound to this local daemon and current safety code. A later
daemon or code change requires a fresh check before any approval decision.

## Exact next engineering step

Turn the two oracle-backed calibrations into separately versioned
matched real-code task families: define a truly removed required capability
for unavailable cells with truthful verifiable feedback; predeclare weak and
held-out strong challenges, insecure mutations, and host-owned oracle rules;
record raw test, strong test, oracle, and benchmark-gate outcomes after every
submission. Add independent expert review of the task contracts, leakage,
mutation coverage, and C5 false-verdict pairing before running any model for
prospective external-validity evidence. Do not reuse the 80-row catalog as if
these corrections were retroactive.
