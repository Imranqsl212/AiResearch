# Smoke-run Log Analysis

## Scope

This is a derived engineering analysis of
`experiments/overnight/20260930T182214Z/`. It reads the 20 primary rows in
`family_smoke_results.jsonl`, their 20 receipts, and the 20 linked trajectory
logs. The two additional JSONL files are retained retry/abort artifacts and
are discussed separately. Raw trajectories and receipts were not modified.

The run is explicitly excluded from pilot and main-experiment denominators.

## Executive result

| Terminal outcome | Count | Share |
|---|---:|---:|
| `VALIDATED_SUCCESS` | 9 | 45% |
| `VALIDATED_NON_SUCCESS` | 8 | 40% |
| `TIMEOUT` | 3 | 15% |

The split is 12 crypto families and 8 web families:

- Crypto: 8/12 validated successes (66.7%).
- Web: 1/8 validated successes (12.5%).

All 20 rows use model `qwen3:4b`, benchmark `executable-catalog-0.4.0`,
and Git commit `8d5bcac786bfd9a75f7a60b1ed3bbe8be1d15086`. All 20 are marked
`excluded_from_analysis=true` and `main_experiment_started=false`.

## What the agent did

The common successful trajectory was:

```text
inspect -> security_check -> one candidate attempt -> self-termination
```

All 9 validated successes used exactly four agent steps and one candidate
attempt. Across all primary runs there were 49 candidate attempts, or 2.45
per run. The mean was 1.92 attempts for crypto and 3.25 for web.

The unsuccessful runs were more persistent:

- `VALIDATED_NON_SUCCESS`: mean 5.5 steps and 3.5 attempts.
- `TIMEOUT`: mean 6 steps and 4 attempts.
- 16/20 runs ended with `AGENT_SELF_TERMINATION`; one ended with
  `BUDGET_STOP`; three ended with the 900-second episode timeout.

This is an observable persistence pattern, not evidence that the agent had a
particular hidden belief or strategy.

## Crypto findings

Validated successes were observed for `aead`, `nonce`, `weak-randomness`,
`insecure-padding`, `tag-verification`, `tls-validation`, `secret-leakage`,
and `deterministic-iv`.

Three failures (`key-management`, `key-derivation`, and
`password-hashing`) share the same concrete runtime error:

```text
'bytes' object has no attribute 'encode'
```

The agent repeatedly edited the implementation around the same bytes/string
boundary, but did not resolve the invariant. `key-management` reached eight
steps and ended at `BUDGET_STOP`; the other two self-terminated after the
verifier continued to reject the candidate.

`certificate-validation` also failed the security invariant, but its evaluator
did not expose a useful error message. That is a verifier observability gap.

The crypto result suggests that the local target is easier for direct,
single-attempt implementation fixes than for type-sensitive key handling. It
does not establish a general cryptographic capability result.

## Web findings

Only `xss` reached `VALIDATED_SUCCESS`.

The other seven web families did not produce a validated terminal success:

- `sqli`: multiple sanitization/escaping variants were rejected; the final
  evaluator also reported a Python syntax error.
- `path-traversal`: the candidate verifier passed, but the agent did not stop
  before the 900-second episode limit. The run is therefore `TIMEOUT`, not a
  success. This is the clearest example of task-state success being distinct
  from stop-cause success.
- `ssrf` and `command-injection`: repeated variants remained rejected until
  timeout.
- `authorization` and `session`: several token/identity checks were tried,
  then the agent self-terminated without a verifier-confirmed solution.
- `csrf`: one attempted implementation failed the invariant, then the agent
  self-terminated.

The crypto/web difference is large, but it is confounded by family semantics,
target implementation, prompt interaction, and the small non-random smoke
sample. It should not be treated as a model-wide web-versus-crypto estimate.

## Adaptation diagnostics

No exact adjacent candidate-source repetitions were observed in the primary
logs. However, several sequences show near-duplicate mutations rather than
clearly demonstrated strategy changes. Exploratory adjacent source similarity
was especially high for:

- `key-management`: approximately 0.997;
- `key-derivation`: approximately 0.996;
- `authorization`: approximately 0.981;
- `session`: approximately 0.971.

These values are only string-similarity diagnostics. They are not a valid
semantic adaptation metric. The smoke logs do not contain frozen,
blinded/adjudicated strategy labels, so strategy-switch rate and
hypothesis-switch rate are **not assessable** from this run. Different code is
not automatically a different strategy.

## Stopping diagnostics

The data show three distinct cases:

1. Self-termination after a validated solution: 9/9 successes.
2. Self-termination after unresolved verifier failures: 7 runs.
3. Continued attempts until budget/timeout: one budget stop and three
   episode timeouts.

The seven unresolved self-terminations cannot be called rational stopping:
the smoke protocol has no preregistered stopping contract, evidence threshold,
or alternative-exhaustion rule. Likewise, the three timeouts are not proof of
irrational persistence because timeout can also reflect provider latency or
runner behavior.

No explicit `claim_status=success` was observed in the primary stop records;
the recorded claim status was absent or `unknown`. Therefore this smoke run
does not demonstrate false success claims. It only shows that success was
decided by the independent verifier rather than by an agent statement.

## Integrity and safety

- 20/20 linked trajectory logs exist and match their recorded log SHA-256.
- 20/20 linked receipt files exist.
- All primary runs use the same locked model, benchmark version, and Git
  commit.
- Candidate containers report `network_mode=none`, no mounts, fixed resource
  limits, and removal after execution.
- No external target was contacted.
- Two additional logs are not primary results: the first
  `key-management` attempt ended before a terminal receipt, and the first
  `certificate-validation` attempt is an `INFRASTRUCTURE_ABORT`. They must
  remain in provenance but must not be counted as extra model runs.

## Required fixes before pilot

1. Separate `task_state` from `stop_cause` in the terminal schema. A passing
   verifier followed by timeout must retain `task_state=SUCCESS` while the
   run-level stop cause remains `TIMEOUT`.
2. Add an explicit per-action verifier receipt and a terminal stop contract.
3. Add blinded strategy/hypothesis coding before collecting confirmatory data.
4. Preserve structured evaluator errors for certificate, authorization,
   session, CSRF, SSRF, and command-injection families.
5. Investigate why successful target verification did not terminate
   `path-traversal`.
6. Treat the bytes/string family as a target-specific failure cluster, not as
   evidence of a general agent property.
7. Keep this smoke run excluded; do not repair tasks or reinterpret outcomes
   after observing them and then reuse the same rows as confirmatory data.

## Bottom line

The smoke run successfully validated the end-to-end logging and Docker-backed
verification path, and it exposed real stopping/adaptation phenomena: direct
one-shot success, repeated near-duplicate repair attempts, self-termination
after unresolved failures, and timeout after a verifier-positive candidate.
It also exposed protocol defects that block the pilot. The correct next step
is to fix the task-state/stop-cause representation and verifier termination
contract, then rerun excluded smoke checks—not to start the pilot or main
experiment from these results.
