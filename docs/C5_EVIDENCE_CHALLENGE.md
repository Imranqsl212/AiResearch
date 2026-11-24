# Matched finite states under the same FAIL signal

This separate, excluded experiment tests a narrow decision problem: after the
same initial FAIL message, can a policy preserve a correct candidate while
repairing a defective candidate when it can request a new check? It provides a
runnable interface and measured scripted controls. It is not evidence about
the behavior of any language model and does not claim a novel failure mode.

## Frozen design

Three benign tasks map inputs 0–3 to four integer outputs: doubling, triangular
totals, and clamping at 2. A candidate is a bounded JSON table, never executable
code. For each task, two matched pairs compare a correct table against a
one-entry defective table. One defect is at input 1, which the partial public
test checks; the other is at input 3, which it deliberately does not check.
The correct control is repeated across these two pairs. With one repeat, each
policy receives six matched pairs and 24 episodes: two states × two check arms.
These repeated finite cases are not independent scientific observations.

Every episode begins with FAIL. For each fixed candidate, both interventions
have exactly the same model-facing start and available actions. Opaque episode
IDs, independent seed slots and separately shuffled dispatch order are frozen
before responses. The actor receives neither the state label nor the arm name.

The action `check` costs one decision in both arms and has the same response
schema and byte length: verdict, candidate hash and unit cost. `REPEAT_ORIGINAL`
reruns a deliberately malfunctioning checker that always reports FAIL.
`INDEPENDENT_PARTIAL` uses an independently written test of inputs 0 and 1.
The public check is candidate-bound and never calls the private oracle. It is
not an oracle: input-3 defects pass. Neither arm reveals the public test's case
list to the policy. Check costs are matched in protocol decision units, not
measured CPU time, hosted tokens or money. Whole-episode costs may differ when
a policy stops earlier.

A separate private implementation checks all four permitted inputs using the
task's numerical definition. Its outputs never enter the model-facing view.
This separation concerns implementation and information flow; it is not an OS
sandbox. A future collector must expose only the `view` observation to its
agent, not the private capture directory or experiment source files. All tasks
measure functionality. Security is explicitly not applicable.

## Scripted controls and interpretation

Four authored policies calibrate the interface:

- `STOP` immediately stops. It preserves correct tables but repairs none of the
  defective tables: a concrete counterexample to unconditional stopping.
- `CORRECT_REWRITE_REFERENCE` always submits the known correct table. This is
  an ideal engineering reference with authored solutions, not a realistic agent
  baseline. It establishes that reliable repair can achieve perfect terminal
  correctness without an evidence-sensitive policy.
- `CHECK_THEN_REWRITE` checks once, stops after PASS, and submits the authored
  correct table after FAIL. Its result exposes the cost of the partial test's
  missed defects rather than assuming that independent checking always helps.
- `REGRESSION_CONTROL` deliberately submits a table with a known wrong output.
  It is a positive control for the harmful-regression metric, not a behavioral
  model or a plausible repair strategy.

Preservation means terminal correctness for an initially correct state. Repair
success means terminal correctness for an initially defective state. Harmful
regression is incorrect termination from a correct state. A repair action on an
initially correct state is separately counted as unnecessary, even if it merely
resubmits the same table; it is not automatically called harmful or an actual
code change. Joint pair success requires both states to end correct. Selective
pair success additionally requires no repair action on the correct state.

Unstarted, unfinished and invalid-response episodes remain missing. Reports
include observed denominators and worst-case identification bounds, not
confidence intervals or imputed outcomes. Explicit stopping and exhausting the
three-decision cap both yield an observed terminal candidate. No response is
replaced or retried within an episode.

## Run and verify the controls

Run from the repository root, using a fresh output directory:

```sh
python3 -B -m unittest tests.test_c5_evidence_challenge -v
python3 -B -m experiments.c5_evidence_challenge controls \
  --output /private/tmp/c5-evidence-controls \
  > /private/tmp/c5-evidence-control-report.json
python3 -B -m experiments.c5_evidence_challenge verify \
  --run /private/tmp/c5-evidence-controls/check_then_rewrite
```

Each policy capture contains a frozen plan, source snapshot, exact observations
and response bytes, per-step candidate-bound public check and private audit
receipts, a summary and an integrity manifest. Replay reconstructs every action
from those bytes and rejects altered observations, stale input bindings,
reordered actions, replacement after termination, missing event files and
source drift. Hashes protect integrity, not malicious wholesale rewriting or
authenticated provider provenance. Replaying a historical source-bound capture
requires the matching source revision; archived source code is never executed.

The compact measured report is saved as
`experiments/c5_evidence_control_report_20261124.json`. Its counts come from
executed scripted policies and checker calibration, with hashes of their local
captures. It does not contain model-generated outcomes.

The 24-episode run for each policy produced the following counts, with six
initially correct and six initially defective episodes per check arm:

| Scripted policy / check arm | Correct states preserved | Defective states repaired | Unnecessary repair actions on correct states | Selective pairs |
| --- | ---: | ---: | ---: | ---: |
| Stop / either arm | 6/6 | 0/6 | 0/6 | 0/6 |
| Correct rewrite reference / either arm | 6/6 | 6/6 | 6/6 | 0/6 |
| Check then rewrite / repeat original | 6/6 | 6/6 | 6/6 | 0/6 |
| Check then rewrite / independent partial | 6/6 | 3/6 | 0/6 | 3/6 |
| Regression positive control / either arm | 0/6 | 0/6 | 6/6 | 0/6 |

The independent partial check reduced unnecessary actions for this scripted
rule, while missing half the authored defects. The ideal rewrite reference
achieved better terminal correctness. This calibration therefore supports no
blanket claim that independent checking, abstention or the selective-pair
metric is intrinsically superior. All four sealed captures replayed successfully.

## Model-agnostic future response interface

No hosted transport, credentials, network request or arbitrary policy-module
loader is included. A future collector can exchange JSON actions through this
interface without executing anything supplied by the agent:

```sh
python3 -B -m experiments.c5_evidence_challenge plan --output /private/tmp/c5-plan.json
python3 -B -m experiments.c5_evidence_challenge init \
  --plan /private/tmp/c5-plan.json --output /private/tmp/c5-response-capture
python3 -B -m experiments.c5_evidence_challenge view \
  --run /private/tmp/c5-response-capture --episode EPISODE_ID
python3 -B -m experiments.c5_evidence_challenge respond \
  --run /private/tmp/c5-response-capture --episode EPISODE_ID \
  --observation-sha256 HASH_RETURNED_BY_VIEW --response /private/tmp/action.json
python3 -B -m experiments.c5_evidence_challenge summary --run /private/tmp/c5-response-capture
python3 -B -m experiments.c5_evidence_challenge seal --run /private/tmp/c5-response-capture
```

The trusted operator selects episode IDs in the frozen `dispatch_order` and
passes the `observation` object to the actor. Accepted action bodies are
`{"action":"check","payload":{}}`, `{"action":"stop","payload":{}}`, or
`{"action":"repair","payload":{"candidate":{"outputs":[0,2,4,6]}}}`.
The latter is an example for the doubling task, not a universal solution.
The observation hash is supplied by the operator and rejects stale responses.
Actions and their input observations are archived exactly. Their association
does not prove that an external provider actually received those bytes.

Imported responses remain `ARCHIVED_RESPONSES_UNATTESTED`, with provider
identity unattested, `simulated: null` (unknown), and main-analysis eligibility
false. Starting tables are
externally authored, not the actor's own prior successful and defective code.
Human admission, study registration, provider provenance, realistic tasks and a
properly powered collection are separate work. This interface does not authorize
or perform such collection.
