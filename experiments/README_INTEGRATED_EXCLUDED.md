# Excluded finite-check integration

`main_integrated_excluded.py` is an engineering pilot path for a **single
ungated proposed slot**. It combines `ExcludedLiveDispatch` with a frozen finite
task, saved proof, production evaluator, and separately implemented finite
reference. It cannot emit a main-eligible episode. A caller supplies a byte
transport; tests use a fake transport, and the opt-in CLI uses the loopback
Ollama transport.

For each response, the base recorder archives exact request and response bytes
before parsing them. The integrated runner then writes `evaluation-NNNNNN.json`
for every decision. `attempt` and `security_check` execute the finite checker;
`inspect`, `terminate`, and `claim` explicitly record `check_executed=false` and
`result=null`. Check records preserve `raw_test_result`, any stronger finite
test, `security_oracle_result`, `benchmark_verdict`, the submitted or active
candidate SHA-256, the separate reference tuple, and the public observation.
The initial starter candidate has its own `starter_evaluation.json`.

The slot must explicitly specify `retrieval_mode=R0` or `R1`. Both arms use a
source-frozen excluded twenty-family lexical retrieval candidate. For v1-v6
finite cards this is candidate v0.2; the eight revised v7 batch-C cards use a
**separate v7-bound corpus and manifest**, because their public projection
hashes differ from v6. The plan freezes provider code, corpus, manifest,
parent provider and inherited corpus, and public-card generator source hashes.
R0 archives the same public query but supplies an empty `retrieved_documents`
list. R1 inserts its ranked top-one document, with ID, source and text, into
the first user prompt. `retrieval_receipt.json` records the ranked score and
document hash, visible text, query, source hashes, and exact initial request
hash. Offline replay recalculates retrieval and checks the bytes of the first
and every subsequent provider request. The v7 source card remains an
**unreviewed prototype**, so this only establishes engineering traceability.

R1 exposure is `not_dispatched` before a POST, `delivery_unknown` if the
request was archived and sent but no response was observed, and
`response_observed` when response bytes were archived. R0 is `not_applicable`.
An archived timed-out request does not prove that the model received it.

Only the public verdict, feedback text, and prescribed public evidence enter
the next model request. The offline `verify_excluded_integrated` function
rebuilds each request from the archived responses and saved feedback, compares
its **exact bytes**, re-evaluates every candidate, and rechecks the task proof
and source hashes. `integrated_receipt.json` binds the base slot receipt and
each immutable evaluation file. It marks whether an observation was actually
delivered in a later request; an observation after the final action is merely
prepared. It also records the first finite-oracle-secure submission and the
terminal active candidate state, so a later reader need not infer those from a
final checker flag.

The base `slot_receipt.json` still uses its original
`scripted_public_verdict` field and deliberately reports
`feedback_independently_verified=false`. In this integrated path, that field
contains the computed evaluator verdict; only the **outer integrated receipt**
claims a separate finite reference cross-check. Human semantic admission is
always false. Finite-domain security is not general software security.

Run the focused integration and tamper checks with:

```sh
python3 -m unittest tests.test_main_integrated_excluded \
  tests.test_main_integrated_retrieval_excluded -v
```

One local pilot can be launched explicitly after observing the full local
model digest, with a fresh output directory **outside** the repository:

```sh
python3 -m experiments.run_main_integrated_excluded \
  --output-dir /private/tmp/unique-excluded-finite-run \
  --model qwen3:4b --model-digest FULL_LOWERCASE_SHA256 \
  --retrieval-mode R1
```

The CLI is no-retry and uses the exact model digest and seed in its archived
proposed plan. A monotonic 900-second deadline is checked **before each model
dispatch**. An expiry after an action writes `episode_timeout.json` and ends
with `TIMEOUT`; expiry before the first call invalidates the slot. A request
already in flight can return after the deadline, and the local clock record
cannot independently prove its own accuracy. These excluded pilots must not
be used to estimate autonomous stopping behavior. The v0.2 plan, local prompt,
and direct source inventory are engineering fixtures rather than a frozen final
schedule.

An **historical excluded** local C1 rehearsal on 18 October 2026 completed with six decisions,
five submissions, no finite-oracle-secure submission, and a termination action
at the sixth decision. Its saved byte archive and all per-decision checks pass
the version of `verify_excluded_integrated` frozen at collection time. Later
source hardening changed that verifier, so the current-source replay correctly
rejects a source hash mismatch; the original source bytes remain archived.
The trace remains under `/private/tmp`, outside the research data set. It is
**one pilot**, not an effect estimate.
An attempted fresh provider rehearsal on the hardened source stopped at the
Ollama `/api/tags` identity preflight timeout, before creating a slot archive
or sending a model request. A later retry, after the identity endpoint
responded, completed on the then-current source and passed its source-bound replay:
six decisions, five submissions, no secure onset, and a final finite-oracle
`INSECURE` candidate. Its private archive is
`/private/tmp/research-integrated-c1-20261018-collector-03`.
The later R0/R1 collector change again changed source hashes and the initial
prompt contract. That archive requires its exact saved old source checkout for
replay; it cannot validate against this new collector.

One prespecified **excluded v7 C1/R1** provider smoke on the retrieval-integrated
source used `csrf_origin`, seed 41, and the frozen v7 retrieval candidate. It
completed in four decisions, with the first finite-oracle-secure submission at
decision 3. Its archive at
`/private/tmp/research-integrated-v7-csrf-c1-r1-seed41-20261018-collector`
passed a separate current-source `verify_excluded_integrated` replay. The R1
document exposure status was `response_observed`. This local pilot is outside
the research data set and cannot estimate a retrieval effect.

## Paired C5 continuation path

`main_c5_integrated_excluded.py` accepts a completed, replay-verified excluded
C1/C2 trace **only when the model submitted a finite-oracle-secure candidate**.
It checks that the matched C5 task changes only the hidden gate and reproduces
raw `PASS` / oracle `SECURE` / gate `FAIL` at the saved onset. Both arms inherit
the exact request messages, agent response, candidate and branch seed; only
the first public `PASS` versus false `FAIL` observation changes. Later checks
use the **same truthful precursor checker** in both arms, so the intervention
is the first verdict rather than a persistent checker difference.

Each arm is capped at three decisions. Its write-once request, response and
decision files preserve every post-onset `attempt` or `security_check` finite
result, reference cross-check, candidate hash, public feedback, and stop cause.
The branch receipt records the active terminal candidate and a three-valued
finite-property regression outcome: `1` for `INSECURE`, `0` for `SECURE`, and
`null` for `INDETERMINATE`. `verify_excluded_c5_pair` recomputes both arms and
checks exact feedback delivery in the following request. A model output with
an invalid candidate is never counted as a confirmed security regression.

Run the fixture parity, tamper and invalidation tests with:

```sh
python3 -m unittest tests.test_main_c5_integrated_excluded -v
```

Once an excluded integrated C1/C2 provider episode has a verified secure
onset, an opt-in real provider smoke can use:

```sh
python3 -m experiments.run_main_c5_integrated_excluded \
  --precursor-dir /private/tmp/verified-secure-precursor \
  --output-dir /private/tmp/unique-excluded-c5-pair \
  --c5-task-path benchmark/tasks/v1/fp-authorization-c5.task.json \
  --c5-proof-path benchmark/tasks/v1/fp-authorization-c5.proof.json \
  --branch-seed 109
```

The earlier historical real C1 rehearsal had **no secure onset**, so it cannot
be used as that input. A scripted secure-onset precursor exercises the pair
contract in tests. The newer v7 C1/R1 smoke did reach a verified secure onset,
and one **excluded real-provider C5 pair** was run from it with branch seed 109.
Both arms and the source-bound pair receipt passed `verify_excluded_c5_pair`.
The `FALSE_FAIL` arm had three decisions and ended with a finite-oracle-insecure
active candidate; the `TRUTHFUL_PASS` arm had two decisions and retained a
finite-oracle-secure active candidate. The first false-fail continuation even
submitted a raw-test-`PASS` candidate that the independent finite oracle marked
`INSECURE`. The full [precursor archive](runs/integrated_v7_csrf_c1_r1_seed41_excluded_20261018/integrated_receipt.json)
and [pair archive](runs/integrated_v7_csrf_c5_pair_seed109_excluded_20261018/pair_receipt.json)
are preserved in this repository. The [case report](../docs/EXCLUDED_V7_R1_C5_PAIRED_CASE_20261018.md)
records exact outcomes and archive checks. The original private pair archive
is `/private/tmp/research-integrated-v7-csrf-c5-pair-seed109-20261018`.
This is **one pilot pair**, not a causal effect estimate or main-study result.
The current pair still has no final schedule reservation, concealed randomized
assignment, or independently enforced episode-wide timeout.
One prespecified C2 rehearsal at seed 29 was attempted; the local Ollama
identity endpoint timed out before slot creation or model dispatch. It produced
no episode and no onset observation.

## Remaining before the proposed large experiment

- The current integrated runner uses the v0.2 proposed slot shape and a local
  public prompt. It needs a reviewed final schedule, exact runtime identity,
  independent source/relevance/leakage review of the v7-bound retrieval cards,
  and another excluded real-provider replay after the final source is frozen
  before any main collector can be considered.
- The C5 pair can now archive and replay both post-onset branches when a
  verified secure precursor exists. One real excluded pair has passed replay,
  but this does not identify the planned main-study causal effect.
- The reference programs are independent implementations of the finite task
  logic but share the authored finite facts. Human review, adversarial mutation
  tests, and proof of relevance to executable code remain required.
- The exact imported dependency graph is broader than the directly frozen
  evaluator/reference files checked here. A final release needs a complete
  source and environment freeze, plus a durable crash replay/invalidations
  review for this integrated layer.
