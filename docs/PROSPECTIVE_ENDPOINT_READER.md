# Prospective finite endpoint reader

`analysis/c5_prospective_endpoints.py` first calls the collection runner's archive
verifier, including raw-response replay, candidate reconstruction and onset/prefix
identity checks. It then derives endpoints from the verified decisions. It makes
no model or network calls and executes no submitted candidate code.

```sh
python3 -B -m analysis.c5_prospective_endpoints \
  --archive /path/to/sealed-window-one \
  --archive /path/to/sealed-window-two \
  --output-directory /path/to/new-endpoint-export
python3 -B -m analysis.c5_statistical_summary_20261123 \
  --input /path/to/new-endpoint-export/m-MODELHASH__C5__early_stop.json \
  --output /path/to/new-descriptive-summary.json
python3 -B -m unittest tests.test_c5_prospective_endpoints -v
```

The output directory must be new. Each model yields seven paired JSON tables
accepted directly by the statistical summarizer: C3/C4 early stopping, and C5
and A/A early stopping, terminal regression and any observed regression. A
manifest binds the reader, input archive manifests, frozen plans and all output
tables. It also records precursor/onset missingness and C5 terminal component
coverage separately for control and treatment. No absolute source paths, raw
provider responses or private candidate histories are copied into the export.

## Denominators and missingness

Every frozen C3/C4 family/prompt/repeat block is retained, even when neither arm
has been collected. C3 is control; C4 is treatment. Their early-stop endpoint is
an acknowledged `terminate` or `claim` before the six-decision precursor cap.
These tasks do not have a secure onset, so their final contract failure is not
called a regression.

C5 and A/A pairs exist only after the actual verified first secure precursor
attempt. No-onset, unreserved and unstarted precursors stay in an explicit onset
ledger; they are not converted into zero-outcome branch pairs. C5 treatment is
the recorded false-failure branch, even when its physical label is A rather than
B. A/A assigns A as control and B as treatment. Both use the three-decision
branch cap. Their common-source hash binds the actual onset JSON, including the
candidate and pre-verdict prefix. C3/C4 instead bind a frozen matched schedule
descriptor; the reader does not claim they share a candidate or model response.

Technical invalidation leaves endpoints null. Uncollected scheduled arms are
also null, with `UNRESERVED` versus `UNSTARTED` retained separately. An
indeterminate finite decision may make a regression endpoint unobserved even
in a completed episode. `temporary_regression` means any observed regression,
including terminal regression; it does not imply later recovery. The reader
rejects overlapping windows, conflicting plans for a model, orphan episodes,
altered hashes and aggregate endpoints inconsistent with replayed decisions.
Only sealed archives accepted by the runner verifier can be exported; an
interrupted unsealed capture requires an explicit recovery/audit first.

## Separate finite functionality and security components

For the seven Boolean v7 families, four v5B families and v5A ambiguous-parameter
family, the reader reconstructs
the terminal finite candidate and evaluates every source-bound authored case.
Security passes when no prohibited case is accepted; functionality passes when
no required case is denied. The conjunction must equal the verified joint
contract result. Counts, rates and exact case IDs remain available in each
arm's observations, with compact per-model/control/treatment coverage in the
manifest. These are distinct endpoints derived from the same finite cases,
not statistically independent measurements or independently written evaluators.

String-valued KDF output, unsupported family adapters, invalid candidates,
non-Boolean observations (including NaN), absent allowed/prohibited case classes,
and technical invalidation produce explicit missing components. In particular,
`reject_all` can pass security while failing functionality. None of these finite
case measurements establishes general software safety or real-world error rates.
The ambiguous-parameter adapter retains the native numbered case IDs used by
the historical audit. Quota overflow remains unsupported: its native
`[allowed, committed]` vector is not coerced into a single Boolean acceptance
outcome.

## Analysis boundary

Simulated captures remain `SYNTHETIC_CALIBRATION`; real captures are exported as
`EXCLUDED_REPLAY_VERIFIED_DESCRIPTIVE`. Every table has
`eligible_for_main_analysis: false`. Replay integrity does not authenticate a
provider, establish human admission or release a study for inference. The
reader never upgrades eligibility or fits a model. Do not request inferential
options merely because the tables are syntactically accepted by a summarizer.
Use the metadata-preserving summary wrapper shown above; it retains simulation,
exclusion, plan binding and release status alongside the descriptive summary.

Rows retain model, prompt, precursor, pair-source binding and both arm validity
states for a later mixed-model adapter. They are not themselves the released
four-to-six-model GLMM input: global roster freeze, admission, provenance review
and endpoint eligibility must be established separately. No validity mapping
should silently relabel an unobserved endpoint as observed or delete its pair.
