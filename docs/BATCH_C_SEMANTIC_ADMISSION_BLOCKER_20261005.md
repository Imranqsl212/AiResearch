# Batch-C impossibility proof: admission blocker

**Status: internal semantic audit, 5 October 2026.** The eight batch-C finite
families are engineering fixtures, not independently admitted scientific task
families. Passing the current structural precheck does not establish a genuine
C3/C4 unrepairability condition.

## Reproducible observation

In [`finite_batch_c_v6.py`](../benchmark/finite_batch_c_v6.py), every C3/C4
task sets `environment.complete_observation=false`. Both `certify_task` and
`evaluate_candidate` require that same Boolean to be true before *any*
candidate can be called secure. The separate
[`finite_batch_c_reference_v6.py`](../benchmark/finite_batch_c_reference_v6.py)
uses the same Boolean gate. With the C3 flag as authored, all eight families
have zero satisfying candidates. Flipping only that flag to true in an
in-memory copy gives one or two satisfying modes in each family:

| Family | Secure modes with authored C3 flag | Secure modes if flag is true |
| --- | ---: | ---: |
| csrf_origin | 0 | 1 |
| nonce_uniqueness | 0 | 2 |
| signature_algorithm | 0 | 2 |
| deserialization_allowlist | 0 | 1 |
| tls_hostname | 0 | 1 |
| key_rotation | 0 | 1 |
| kdf_salt | 0 | 2 |
| environment_injection | 0 | 1 |

This check is diagnostic only: it does not prove the flag *cannot* represent a
real observation constraint. The current artifacts do not define the claimed
observation mapping, show a pair of indistinguishable worlds demanding
different decisions, or derive the contradiction from candidate-visible
environment behavior. `certify_task` instead emits the same schematic
`required_decisions=[true,false]` for each family once the Boolean gate has
removed all candidates. For `kdf_salt`, even the two listed case labels both
have expected value `true`, so that particular witness is not derived from
the listed case expectations. `verify_proof` compares a saved proof with the
same function's regenerated output; its hash is an integrity check on this
calculation, not an independent semantic impossibility argument.

The master research requirement forbids defining unreachability only with a
hidden reachability flag. This implementation has that risk. **Do not admit
these eight C3/C4 families or describe them as independently proven
unrepairable on the basis of the existing machine certificates.** The
existing excluded pilot results remain engineering observations and are not
promoted to main data.

## Required repair before review

1. Specify the candidate-visible observation function and the allowed action
   language for each family. State the two or more admissible environmental
   worlds and security decisions that would conflict under the same
   observation, or provide a complete independent exhaustive argument.
2. Implement the oracle so its truth follows from those worlds/cases rather
   than from a task-level `complete_observation` veto. Keep the evaluator and
   oracle independently implemented, then challenge both with mutations.
3. Version new task, proof, evaluator, reference, indexes, and retrieval
   inputs. Preserve the v6 artifacts and their excluded pilot provenance.
4. Have two independent experts review the replacement as described in the
   [admission packet](HUMAN_ADMISSION_REVIEW_PACKET_20261005.md). Any rejected
   family requires a new version or a narrower design and power decision.

A separate [v7 semantic candidate](BATCH_C_V7_SEMANTIC_CANDIDATE_20261005.md)
now implements explicit same-observation world pairs for all eight families
and passes finite structural checks. It preserves v6 bytes and is **not**
human-admitted, main-bound, or a retroactive repair of the excluded v6 pilots.

The command below reproduces the count comparison without writing files or
running a model:

```sh
python3 - <<'PY'
from benchmark.finite_batch_c_v6 import build_reference_tasks, certify_task
for task in build_reference_tasks():
    if task['condition'] != 'C3':
        continue
    authored = certify_task(task)
    changed = {**task, 'environment': {'complete_observation': True}}
    flipped = certify_task(changed)
    print(task['family'], len(authored['satisfying_candidates']),
          len(flipped['satisfying_candidates']))
PY
```
