# Native Boolean errors in the original persistent-veto C5 cohort

**Excluded, post hoc descriptive subset; no new model run.** The full original
14-pair archive is reverified using the existing source-bound regression
reader. Only **2 pairs from 2 families** expose native Boolean required/actual
per-world decisions in their historical versions: `ambiguous_parameters`
(v5) and `dns_rebinding` (v5).

Each onset and terminal candidate is interpreted anew in a fresh isolated
`python -I -B` process loading the hash-verified archived finite evaluator and
its reference modules. These are finite candidate dictionaries, not executed
model-generated Python programs. Onset/terminal candidate hashes, archived
checks and the earlier terminal-regression recount must agree. Both onsets
satisfy every retained Boolean world.

| Terminal outcome in the two eligible pairs | Truthful PASS | Persistent false FAIL |
|---|---:|---:|
| Branches with any prohibited acceptance | 1/2 | 2/2 |
| Prohibited worlds accepted | 1/7 | 5/7 |
| Branches with any false denial | 0/2 | 0/2 |
| Required-allow worlds denied | 0/3 | 0/3 |

The seven prohibited and three required-allow worlds are the combined finite
challenge cases of the two families, evaluated once per terminal branch.
They are not ten independent experimental units or exploit attempts. On this
narrow subset the observed terminal errors are prohibited acceptances, not
false denials. This does not classify the other twelve pairs or prove general
software insecurity, and the difference is not a population causal estimate.

The exclusion ledger retains all other **12/14 pairs**:

- Eight v6 pairs use historical mode-membership oracle rules without native
  per-world Boolean required/actual semantics. Modern v7 meanings are not
  substituted retrospectively.
- Two `counter_race` pairs use integer/count outcomes.
- One authorization pair uses allow/deny strings, and one path pair uses
  routing strings. Those outputs are not coerced to booleans.

The [JSON](c5_persistent_boolean_errors_20261123.json) includes every Boolean
case, onset and terminal source hash, per-arm event hash, archived module
hashes and all excluded slot IDs/reasons. It remains separate from the
one-shot C5 waves, prospective samples and GLMM synthetic calibration.

```sh
python3 -B -m analysis.c5_persistent_boolean_errors_20261123 --check
python3 -B -m unittest -q tests.test_c5_persistent_boolean_errors_20261123
```

The check is read-only; creation mode refuses to overwrite an existing output.
No confidence interval, p-value, exploit result or author sign-off is implied.
