# Prospective finite-mode collection

This entrypoint extends the existing finite C5 first-secure-onset experiment. It
uses the same task registry, public observations, action parser, and durable
archive helpers; historical runners and evidence remain unchanged. Every actual
candidate-state measurement goes through `benchmark.isolated_finite_oracle` in a
fresh Python process. Candidates are finite JSON mode selections, never Python
or shell programs. This process separation is not a sandbox for arbitrary code.

The default eight v7 families and optional broader roster are engineering tiers. **Every output remains
excluded from main analysis**, even when the collection gate passes. Collection
permission does not grant task admission, sufficient statistical power, or a
scientific release. Existing draft registrations and pending review forms cannot
open the hosted gate.

## One-command model-free check

From the repository root, using a fresh output directory:

```bash
python3 -m experiments.prospective_finite validate --output /private/tmp/c5-finite-smoke
```

This validates the complete balanced 480-slot schedule and executes 12
representative simulated runner paths (four conditions × three policies/prompt
variants). It independently replays finite results, raw requests/responses,
candidate-origin evidence, first-onset identity, and branch histories. The
policies are stop, continue, and seeded random **after an explicitly authored
first-attempt calibration fixture**. They are not model observations. Separate
unit tests verify immediate stop without a forced attempt. C3/C4 have no eligible
C5 onset. The finite measurement calibration over all registered C1/C5 candidate
spaces is separately available in `analysis/prospective_c5_finite_calibration.py`.

```bash
python3 -m unittest tests.test_prospective_finite tests.test_isolated_finite_oracle -v
python3 -m experiments.prospective_finite verify --output /private/tmp/c5-finite-smoke
```

No command above contacts a provider, starts a model, or executes candidate code.
Outputs are never overwritten. Preserve failed slots; do not retry or replace
them. The manifest protects integrity relative to its recorded hashes, not
authenticity against an actor who can rewrite the entire archive and source plan.

For the broader roster, the same command validates all 95 source task/proof pairs
and runs C1/C2 forks plus C3/C4 paths for every one of 19 families:

```bash
python3 -m experiments.prospective_finite validate --roster broad19 --output /private/tmp/c5-broad19-smoke
```

The broader smoke has 84 simulated precursor paths: four stop-policy paths per
family plus the default CSRF continue/random cases. It checks C5 and A/A forks
from both repairable conditions. This is engineering coverage, not 84 model
episodes or evidence of independent task-family validity.

## Freeze a proposed hosted schedule

Choose a real model identifier and its explicit HTTPS Chat Completions endpoint.
Commit the implementation before creating the final plan; changes to any bound
source invalidate its replay. This example uses shell variables supplied by the
operator, not a fabricated model or endpoint:

```bash
python3 -m experiments.prospective_finite plan \
  --model "$MODEL_ID" --endpoint "$CHAT_COMPLETIONS_ENDPOINT" \
  --repeats 5 --prompt-count 3 --output /private/tmp/c5-plan.json
```

One plan describes one model stratum: eight families × C1/C2/C3/C4 × three prompt
variants × five repeats = 480 six-decision precursors. Each C1/C2 precursor may
contribute its first agent-issued independently `SECURE`, raw-`PASS` attempt.
Every such onset reserves one C5 pair and a separate A/A pair, each with three
decisions per branch: at most 240 onset pairs of each kind and 5,760 generation
calls per model. Missing onsets stay missing; authored controls never substitute
for them. C4 versus C3 remains a distinct prescheduled contrast.

Add `--roster broad19` to `plan` to select authorization v1, path-boundary v2,
transaction replay v3, the eight batch-A/B v5 families, and eight batch-C v7
families. The roster deliberately excludes counter-race v4 and duplicate batch-C
v6 versions. It has 1,140 precursors, 570 potential C5 pairs, 570 separate A/A
pairs, and at most 13,680 generation calls per model (54,720 for four model
strata). The planner verifies catalog hashes, regenerated finite certificates,
semantic C1/C2/C5 identity, and public C1/C5 and C3/C4 parity. Some older families
use finite tables or bounded state machines rather than single modes. Batch-A
C3/C4 certificates exhaust the permitted candidate space with environment
witnesses and counterexamples; they are not claims of unrestricted impossibility.

C5 branches share the same candidate, exact pre-verdict transcript, and scheduled
seed; only the assigned initial verdict and its text differ. Subsequent checks
are truthful. A/A branches share the same transcript and PASS feedback but use
distinct prescheduled seeds to assess repeat variability. Scheduling and branch
order are fixed before outcomes; A/B mapping is not exposed to the model. The
default sends no seed because support varies across providers. `--send-seed`
enables best-effort seed requests, explicitly recorded as **unverified**. Distinct
scheduled seed numbers do not establish independent generations. Repeated
deterministic outputs must not be represented as independent behavioral evidence.

The default request uses `max_completion_tokens=256`, `temperature=0.3`, no
streaming, a 60-second request timeout, a 420-second episode limit, and no retries.
Provider compatibility is explicit: `--omit-temperature`,
`--token-parameter max_tokens`, `--max-output-tokens`, and repeated
`--accepted-model` values are frozen in the plan. Returned model IDs must match
the accepted list. Returned ID, completion ID, fingerprint, token usage, and
provider finish reason are preserved when available; these are provider claims,
not independently verified weights. `finish_reason=stop` ends a completion; only
the parsed finite `terminate`/`claim` action requests workflow termination.

## Admission and registration gate

Hosted collection requires all of the following before its first generation:

1. Completed, consistent independent review and adjudication CSVs for every
   scheduled family, accepted by the existing validator against reviewed source
   commits. Pending or rejected selected families block dispatch. The validator
   projects the shared full register onto the frozen roster without creating any
   review data; original and projected hashes and omitted families are recorded.
   An unrelated pending counter-race row does not block the broad19 roster.
2. An identified human's explicit approval bound to the exact plan, review,
   adjudication, and final protocol bytes. This is an operator attestation; the
   program does not authenticate the person's identity or review independence.
3. An approved, nonwithdrawn OSF registration dated before collection, either
   public or an approved embargo accessible with an explicitly supplied read
   token. The gate reads official OSF API metadata, and the designated immutable
   answer field (`summary` by default) in `registration_responses` or
   `registered_meta` must contain the literal lines
   `plan_sha256: <exact plan-file SHA256>` and
   `preregistration_sha256: <exact protocol-file SHA256>`. Editable descriptions
   alone are insufficient. Both direct strings and nested `{value: ...}` answer
   schemas are supported. This gate does not silently accept a draft, unapproved
   reservation, an inaccessible private project, local timestamp, or unsupported
   registry. For embargoed records, `--osf-token-env OSF_READ_TOKEN` explicitly
   names the environment variable containing a read token. It is sent only to
   the fixed `api.osf.io` metadata endpoint, never archived or printed.

An approval file has the following schema. These **pending placeholders cannot
authorize a run**; a real reviewer/operator must supply genuine evidence:

```json
{
  "status": "PENDING",
  "plan_sha256": "PENDING",
  "review_register_sha256": "PENDING",
  "adjudication_register_sha256": "PENDING",
  "preregistration_sha256": "PENDING",
  "independent_human_reviews_confirmed": false,
  "collection_has_not_started": false,
  "admitted_families": [],
  "approver_name": "PENDING",
  "approver_role": "PENDING",
  "independence_verification_basis": "PENDING",
  "approved_at": "PENDING",
  "osf_registration_id": "PENDING",
  "osf_answer_field": "summary"
}
```

Approved status is `APPROVED_FOR_BOUNDED_COLLECTION`; timestamps must be ISO 8601
with a timezone. The gate archives its exact metadata and file hashes. No paid
calls have been made as part of implementing or testing this entrypoint.

Only after genuine admission, registration, and authorization:

```bash
python3 -m experiments.prospective_finite run \
  --plan /private/tmp/c5-plan.json --approval /private/tmp/c5-approval.json \
  --review-register /path/to/completed-review.csv \
  --adjudication-register /path/to/completed-adjudication.csv \
  --preregistration /path/to/final-registered-protocol.md \
  --output /path/to/new-private-capture --start-slot 0 --max-slots 1
```

The API key is read from `OPENAI_API_KEY` (override its variable name with
`--api-key-env`). Authorization headers and key values are never archived. A
one-slot smoke is a partial engineering capture, not the complete balanced
cohort. Slots outside that window are explicitly reported. Continue using a new
output directory and `--start-slot 1` with the desired `--max-slots`. These are
zero-based offsets in the frozen shuffled schedule, not numerical slot-ID suffixes.
The shared allocation ledger defaults to `.finite-allocation-<plan SHA256>` beside
the plan file; `--allocation-dir` can name a fixed shared location. Retain and
reuse that same ledger across windows. Every selected slot is durably consumed
before dispatch, and overlapping windows are rejected even if a prior process
failed before contacting the provider. Reservations and technical partials are
auditable missing data; there is no replacement mode. Deleting or changing the
ledger is not a legitimate continuation. A connection timeout leaves delivery
unknown, since a remote provider may still have processed the request.

For each step, request bytes and a dispatch-start receipt are fsynced before
transport, raw returned bytes before parsing. Finite oracle receipts distinguish
an agent-requested check from hidden audit measurement on inspect/finish steps.
Terminal receipts separate the assistant's finish request from controller budget,
wall-clock, or infrastructure termination. Invalid finite candidates remain
`INDETERMINATE`; they are never counted as confirmed regression. Replaying an
archive checks each branch against its actual earliest precursor onset as well
as checking every finite result and delivered message.

Protocol references: [OpenAI Chat Completions API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
[official OSF API](https://developer.osf.io/). Compatibility must be assessed for
the selected provider before a registered collection; hosted seed adherence and
cross-provider model identity cannot be inferred from this adapter alone.
