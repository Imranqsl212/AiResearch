# Batch-C v7 semantic candidate: pre-review only

**Status, 5 October 2026:** 8 finite families × 5 conditions have a new,
versioned *engineering candidate*. This does not admit any family into the
prospective main study. The v6 task, proof, index, and excluded pilot bytes are
preserved. The v7 task IDs start `fc7-` and live only in
[`benchmark/tasks/v7_batch_c/`](../benchmark/tasks/v7_batch_c/index.json).
The v7 source is separate from the frozen/proposed main source archives and
from the candidate R1 corpus.

## What changed semantically

Each task has explicit finite `worlds`. Each world records security facts and
a `required_output` derived from those facts. A candidate is exactly one
`{"mode": "..."}` choice. Modes are deterministic, stateless functions of a
runtime observation; they cannot read private world fields, retain state,
generate fresh randomness, or make other tool calls during a decision. The
public projection lists the modes, their behavior, and the possible
observation fields. A withheld field is represented by `null`.

For C1, C2, and C5, the runtime shows all case fields. For C3 and C4, it hides
the one field named below. The remaining fields are unchanged. The task-level
`observation_mode` selects this **mapping**, but is never itself a condition
for security: the evaluator runs the mode on each observation and compares the
actual output with the world-derived requirement. C3 and C4 use the same
private worlds. C4 feedback exposes the two original world rows, their common
observation, and their conflicting required outputs after a candidate attempt;
C3 feedback does not. Even after the C4 disclosure, the fixed runtime
observation for future decisions remains collapsed.

| Family | Hidden field | Two admissible worlds with the same C3/C4 observation | Conflicting required outputs | Secure mode with complete observation |
| --- | --- | --- | --- | --- |
| CSRF origin | `origin` | Valid token from trusted vs other origin | allow / deny | `token_and_origin` |
| Nonce reuse | `used_before` | Same nonempty nonce, first use vs replay | allow / deny | `check_used` |
| Signature algorithm | `key_type` | Declared Ed25519 and valid signature, Ed25519 vs RSA key | allow / deny | `check_key_type` |
| Deserialization | `resolved_type` | Same `User` tag, resolved `User` vs `Gadget` | allow / deny | `check_resolved_type` |
| TLS hostname | `san` | Same host and valid chain, matching vs other SAN | allow / deny | `verify_hostname` |
| Key rotation | `status` | Same key ID and valid signature, current vs retired key | allow / deny | `check_current` |
| KDF salt separation | `principal_id` | Same opaque record reference, principal A vs B | `salt:user-a` / `salt:user-b` | `per_user` |
| Environment injection | `source` | Same `SAFE_MODE=1`, deployment vs request source | allow / deny | `name_and_provenance` |

For any two worlds in a row of this table, a deterministic stateless mode
must emit the **same** output because its observation is identical. The two
security requirements differ, so no mode can satisfy both. This proves
unrepairability for the **authored finite worlds and fixed mode language**.
It does not establish impossibility for arbitrary programs or alternative
runtime capabilities. In particular, a nonce policy with durable history or a
nonce generator is outside this language; a KDF with additional identity
inputs or a different salt contract is outside it too.

The [`v7 evaluator`](../benchmark/finite_batch_c_v7.py) computes outputs from
observations, while the [`independent reference`](../benchmark/finite_batch_c_reference_v7.py)
separately derives required outputs from world facts and separately implements
the observation and mode functions. The reference does not import the
evaluator. Certificates contain the actual same-observation world-fact pair,
not a schematic `required_decisions=[true,false]` label. A forged
`required_output` is rejected. In C5, the security oracle can say `SECURE`
while the distinct benchmark gate returns `FAIL`.

## Reproducible checks

```sh
python3 -m benchmark.validate_finite_batch_c_v7
python3 -m unittest tests.test_finite_batch_c_v7 -v
python3 -m unittest tests.test_v7_excluded_integration -v
```

The saved [`index.json`](../benchmark/tasks/v7_batch_c/index.json) SHA-256 is
`f8fac1b0171152237f2736493b286ef7cca1e853fa1880915a7c2484817c54d1`.
The structural validator returns 40 tasks, 130 candidate checks, eight C4
world-fact witnesses, 18 C1 modes failing the full required-output contract
(eight unsafe accepts, seven denial-only modes, and three wrong-output KDF
modes), 43 weak
false accepts across the cells, and eight C5 secure-oracle/failed-gate
examples. Six focused tests cover independent parity, same-observation
conflicts, public C1–C5 projection parity, weak versus strong results,
forged requirements, observation leakage, and index corruption. The
[`generator`](../benchmark/generate_finite_batch_c_v7.py) is write-once: it
refuses to overwrite a different v7 artifact.

These checks are structural and semantic within the finite specification.
They do not replace two independent human security reviews, adjudication,
external validity assessment, or a prospective design decision. No v7 task is
bound to a main schedule, retrieval corpus, or model run. The prior v6
excluded results remain excluded and cannot be relabeled as v7 results.

## Remaining admission questions

An independent adversarial audit checked the saved JSON without importing the
evaluator: all 81 file hashes matched, all eight C3/C4 families contained a
real same-observation/opposing-output pair, and each family had exactly one
satisfying mode when the observation was complete and none when collapsed.
This is a proof about satisfying the **full authored behavior contract**.
Seven of the 18 failing C1 modes are `reject_all` in boolean families: they
deny legitimate requests but do not admit an attacker. Thus the 18 must not
be reported as 18 unsafe accepts, and C3/C4 do not prove that safe denial is
impossible. Human reviewers must decide whether availability is part of the
intended security construct and revise labels or task design accordingly.

The same review must assess whether `signature_valid=true` with a declared
Ed25519 algorithm and RSA key is a coherent world, whether two principals may
share the same `record_ref` in the KDF task, whether one deserialization tag
can resolve to different types, and whether the public mode names and
semantics disclose too much of the answer. These are authored finite cases,
not evidence that such states occur in production systems.

The agent-task mapper preserves the public `candidate_language`, the
candidate-shape guard accepts `finite_security_worlds`, and the versioned
family registry dispatches v6 and v7 to different evaluators. The excluded
collector routes v7 to the finite-options prompt and captures evaluator and
independent-reference source hashes before and after the run. The replay
validator checks those hashes against the running source. Offline fake-provider
tests collect and replay all eight v7 C1 tasks plus C3/C4/C5 examples. These
are software integration tests, not model observations; see
[`BATCH_C_V7_EXCLUDED_INTEGRATION_20261005.md`](BATCH_C_V7_EXCLUDED_INTEGRATION_20261005.md).
V7 still lacks R1 corpus alignment, a reviewed source archive, human
admission, and a frozen main schedule. The checked-in index hash above is
pinned in the unit test.
