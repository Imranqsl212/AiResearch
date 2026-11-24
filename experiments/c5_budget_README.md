# Verdict × advertised continuation budget

This separate engineering experiment asks whether one extra **advertised and
enforced** decision changes the effect of a false failure on preservation of a
correct finite candidate. It does not modify the earlier C5 study, its data,
registration packet, or runtime source files. It has no collected model results
and never marks an observation eligible for main analysis.

Each completed C1/C2 precursor contributes its earliest agent-issued attempt
with independently verified `SECURE` and raw `PASS` results. Four fresh
continuations receive the same exact pre-verdict transcript and candidate:

| Cell | First verdict | Advertised and enforced new decisions |
| --- | --- | ---: |
| PASS2 | Truthful PASS | 2 |
| PASS3 | Truthful PASS | 3 |
| FAIL2 | False FAIL | 2 |
| FAIL3 | False FAIL | 3 |

The message explicitly ends the precursor phase and replaces its six-decision
limit. Repeated public task cards may retain that earlier metadata; the new
instruction explicitly says these values do not reset the continuation budget.
Every later requested check is truthful. No branch is inferred by truncating a
three-decision trace: the advertised budget can change the first response.
Condition IDs, onset truth, proof candidates, private oracle results, and branch
labels are absent from model-visible messages.

The default proposed roster has 19 finite families, two precursor conditions,
three prompt variants, and five repeats: 570 precursor slots per model. Each has
at most six precursor decisions plus ten continuation decisions, giving 9,120
generation requests per model. The existing eight-family roster remains an
option. Every block uses a common scheduled branch seed across its four cells;
provider seed adherence remains unverified. A randomly relabeled four-sequence
Williams design counterbalances execution position within family, with at most
one-position-count imbalance in incomplete cycles. Execution order is archived
before branch dispatch.

The terminal endpoint is finite joint correctness, not unrestricted program
security. A completed finite `INDETERMINATE` candidate has null correctness;
technical failures are missing, never incorrectness zeros. Early stop means an
actual terminate/claim action before the assigned cap. A stop on decision two is
therefore early under cap three but not under cap two; cross-budget early-stop
comparisons alone have a mechanical threshold difference. The primary factorial
question should concern terminal correctness. The intervention combines the
advertised horizon and actual opportunity; it does not separate their effects.

Completed precursors with no secure attempt produce `NO_ONSET`. A technically
invalid precursor produces `TECHNICAL_INVALID`, even if its valid prefix had a
secure attempt; `observed_secure_prefix` retains that fact. These are separate
pre-assignment missingness categories. All four reserved cells remain present as
`UNSTARTED`, with explicit reasons. No missing precursor or branch is replaced.

## Offline commands

```bash
python3 -B -m unittest tests.test_c5_budget_runner -v
python3 -B -m experiments.c5_budget_runner calibrate --output /private/tmp/c5-budget-calibration
python3 -B -m experiments.c5_budget_runner verify --output /private/tmp/c5-budget-calibration
```

Calibration uses 12 explicitly simulated blocks in one family, crossing C1/C2
with six policies: stop, continue, budget-sensitive stopping, damage only at the
third false-failure decision, an injected transport failure, and no secure onset.
The damage control has terminal correctness PASS2=PASS3=FAIL2=true,
FAIL3=false. The budget-sensitive control produces different first actions at
budgets two and three. Failure and no-onset controls check missingness rather
than manufacturing behavioral outcomes. No model or network call is involved.

The new verifier reconstructs task starts, the earliest qualifying raw response,
candidate/origin bindings, all four initial verdict/budget messages, dispatch
order, and block endpoints. It then copies only episode files into a temporary
verification view and delegates per-decision finite replay to the unchanged
previous runtime verifier. The temporary view does not invent or modify an
observation. The new wrapper owns factorial pairing; the old verifier owns
individual episode replay. Hashes provide integrity, not independent attestation
of a provider or a person's identity.

`verify_archive(Path)` returns a source-verified summary with `blocks[]`, a stable
model identifier, explicit `simulated`/`data_kind`, and per-cell verdict, budget,
status, nullable terminal correctness, observed costs and stopping fields. This
is the interchange format for `analysis/c5_budget_*`. Branch status is `VALID`,
`TECHNICAL_INVALID`, or `UNSTARTED`; valid indeterminate candidates still have a
missing correctness endpoint. A logged finish request during a later technical
failure is retained as raw provenance, not automatically a valid stopping
outcome.

The summary also includes the complete `scheduled_roster`, including slots
outside the captured window. Disjoint windows may be combined only for the same
exact plan and model, with no overlapping block IDs. Unattempted scheduled slots
remain separate from completed `NO_ONSET` and technical failures. The verifier
rejects unsealed partial blocks or extra episodes; retain these incomplete
captures for audit instead of silently dropping or replacing them.

## Future hosted route

Prepare a new plan using an actual supported model identifier and endpoint:

```bash
python3 -B -m experiments.c5_budget_runner plan \
  --model "$MODEL_ID" --endpoint "$CHAT_COMPLETIONS_ENDPOINT" \
  --roster broad19 --output /private/tmp/c5-budget-plan.json
```

The plan binds both the unchanged prior runtime plan and the new runner source,
plus Python implementation, version, platform, and executable hash. Collection
requires that runtime identity. Offline replay may use another interpreter while
preserving original runtime provenance and verifying finite results.

The `run` subcommand requires the existing genuine independent-review and OSF
registration gates, applied to **this new plan's exact bytes** and protocol.
An approval for the previous study cannot authorize the factorial extension.
Public and authenticated approved embargoed registrations are supported exactly
as in the original gate. API credentials remain outside archives. The same
durable per-plan allocation ledger prevents overlapping windows and retrying
consumed slots.

After genuine review, preregistration, an explicit compute budget and collection
authorization, the interface is:

```bash
python3 -B -m experiments.c5_budget_runner run \
  --plan /private/tmp/c5-budget-plan.json \
  --approval /path/to/new-plan-approval.json \
  --review-register /path/to/completed-review.csv \
  --adjudication-register /path/to/completed-adjudication.csv \
  --preregistration /path/to/new-registered-protocol.md \
  --start-slot 0 --max-slots 1 --output /path/to/new-private-capture
```

This is a bounded collection route, not evidence that collection has occurred or
that the scientific release gates have been met. All current receipts are
simulated engineering calibration. Retain private captures, allocation ledgers,
technical partials, and exact source snapshots for review.
