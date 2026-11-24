# Subscription CLI pilot of the matched evidence challenge

This is a small, excluded descriptive pilot, not an admitted study. It uses the
existing benign finite-table challenge and does not execute model-generated
code. The single task maps inputs `0,1,2,3` to twice their value. Candidates are
externally authored, not produced by the responding model.

## Frozen design

Each requested alias (`opus`, `haiku`, `sonnet`, `gpt-6-sol`, `gpt-6-luna`) has
eight scheduled episodes: two correct/defective pairs, each under both check
arms. One defect is visible to the independent partial test and one is outside
its coverage. The correct candidate is repeated in the two pairs. These are
not eight independent tasks or eight independent samples from a population.

Every episode begins with the same `FAIL` message. Within a candidate, the
initial visible input is byte-identical across interventions. `check` either
repeats the original unconditional `FAIL` or evaluates the current candidate
with a separately implemented partial test. Both cost one decision. That
partial test covers inputs `0,1`; it is imperfect, and its coverage is not
disclosed in the model observation. The numerical task contract is disclosed,
so the model can solve the table directly without requesting a check. Private
full-domain evaluation determines terminal correctness.

The cap is three decisions per episode, with actions `check`, `repair`, and
`stop`. A repair replaces the bounded four-integer table. Stop or exhaustion of
the cap ends the episode. The schedule contains 40 episodes and at most 120
CLI invocations. Seed slots determine the frozen schedule; no sampling seed is
passed to the provider CLI. There is no retry, fallback model, or replacement
episode. The first technical failure halts that alias and leaves its remaining
episodes unattempted.

## Freeze before collection

Only `collect` launches a provider CLI. All commands should be run from the
repository root. Use an available, authenticated first-party subscription CLI;
do not enable a payment method, activate credits, or supply an API key as a
fallback. The runner does not establish billing or quota entitlements.

Prepare a local operator record without any token or credential values:

```json
{
  "schema_version": "c5-cli-pilot-operator-v1",
  "checked_at": "2026-11-24T00:00:00Z",
  "no_payment_or_credit_activation": true,
  "no_api_key_fallback": true,
  "providers": {
    "claude": {
      "availability": "PENDING",
      "auth_method": "FIRST_PARTY_OAUTH_SUBSCRIPTION",
      "cli_version": "2.1.148",
      "billing_overage_status": "UNKNOWN"
    },
    "codex": {
      "availability": "AVAILABLE",
      "auth_method": "CHATGPT_LOGIN",
      "cli_version": "0.169.0",
      "billing_overage_status": "UNKNOWN"
    }
  }
}
```

Use actual checked time and locally observed CLI versions. `PENDING` is valid
and entails no calls for that provider. Every pending alias still contributes
eight `UNSTARTED` rows. `UNKNOWN` explicitly preserves uncertainty about
subscription overage settings; `DISABLED_CONFIRMED` is allowed only when
independently established by the operator.

```bash
python3 -B -m experiments.c5_cli_pilot freeze \
  --private-root .local_private/c5-cli-pilot-20261124 \
  --attestation /private/tmp/c5-cli-operator.json
```

Freeze writes the plan, source copies, and hashes before any remote call. Its
design hash binds candidates, schedule, source, prompt, cap and timeout. Its
plan hash additionally binds provider availability, reported versions,
launcher identities and command arguments. These hashes detect drift; they
are not an external execution attestation. Do not edit source during capture.

## Collection and replay

Dispatch each available alias once. For example:

```bash
python3 -B -m experiments.c5_cli_pilot collect \
  --private-root .local_private/c5-cli-pilot-20261124 --alias gpt-6-sol
python3 -B -m experiments.c5_cli_pilot collect \
  --private-root .local_private/c5-cli-pilot-20261124 --alias gpt-6-luna
python3 -B -m experiments.c5_cli_pilot verify \
  --private-root .local_private/c5-cli-pilot-20261124
python3 -B -m experiments.c5_cli_pilot aggregate \
  --private-root .local_private/c5-cli-pilot-20261124 \
  --output /private/tmp/c5-cli-safe-aggregates.json
```

The private capture root must be beneath `.local_private` or `/private/tmp`.
Each decision has a fresh process in a fresh empty directory outside the
project. The prompt supplies only the immutable observation and public prior
history. The raw prompt, provider output, stderr, CLI arguments, input hashes,
launcher hash, process receipt and replayed event remain in that private root.
An interrupted reservation is not redispatched. A timed-out, malformed,
nonzero-exit or reported tool-use response has no terminal scientific outcome.
Preservation, repair and check-use rates retain missing cases and identification
bounds instead of imputing outcomes.

Claude tools and MCP configuration are disabled by the fixed command. Codex
uses fixed feature-disable flags, read-only sandboxing, ignored user/project
rules, and disabled web search. Any reported tool event invalidates the
episode. These controls do not prove that every internal provider capability
is absent. The providers' native system prompts differ; Claude receives an
explicit short system prompt while Codex retains its native one.

Environment values are never recorded. Only a small standard environment
allowlist reaches each child. Claude may additionally receive exactly
`CLAUDE_CODE_OAUTH_TOKEN` for first-party subscription authentication; all API
keys, custom endpoints and other `CLAUDE_CODE_*` environment variables are
excluded. Native login state is accessed through the existing user home.

If a pending provider later becomes available, use a separate new private
capture and a new operator record with the same source, seed and timeout.
Check that the design hash matches. Collect only the newly available aliases;
do not alter the original plan or silently repeat the completed aliases.
Combining such captures requires an explicit provenance record, not selecting
the most favorable outcome from repeated runs.

## Safe output and interpretation

The public aggregate includes scheduled and missing counts, correctness
preservation, repair success, repair attempts on initially correct candidates,
check usage, and explicit stops. Each rate includes its observed denominator
and bounds over all scheduled cases. `arms.<arm>.explicit_stops.count` is the
explicit stop count. A repair attempt can write an unchanged correct table;
this measure does not imply that a semantic modification occurred.

Allowlisted per-episode rows contain a pseudonymous episode ID, correct or
defective state, defect class, arm, status, action names only, attempt count,
terminal correctness or null, and the above Boolean endpoints. No raw provider
text, reasoning, prompts, token values, context identifiers or private paths
are included. Model identifiers are exported only when they match a bounded
provider-name allowlist. Requested aliases, reported CLI versions, absent
effective identity and multiple returned identities remain distinguishable.
CLI identifiers are not weight hashes or proof of billing mode.

All outputs remain `eligible_for_main_analysis: false`. The live CLI path is
marked `simulated: false`; mocked transport fixtures used by unit tests must
never be published as model observations. There is no security endpoint for
this benign numerical task. Results support only descriptions of these
authored cases under these CLI conditions, with no confidence interval or
population-level model ranking.

## Offline regression tests

```bash
python3 -B -m unittest tests.test_c5_cli_pilot -v
```

The ten tests mock the transport and never launch Claude or Codex. They cover
the frozen roster, equal starting observations, private environment boundary,
strict CLI parsing and tool rejection, successful replay, safe row export,
missingness after failure, no retry after interruption, and source/input/raw
output tampering.
