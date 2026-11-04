# One missing test can change the answer in every authored task family

**New excluded experiment, 4 November 2026.** We stress-tested the eight
authored v7 Batch-C finite task families by deleting each world from the
checker one at a time. This is an exhaustive test of the **fixed bounded
candidate modes**, not a new agent run or an estimate for real software.
The tasks still lack independent human semantic admission.

The program first validates the exact task index, task files, and proof files.
For each family it enumerates every candidate mode under the full C1
repairable task and the C3 withheld-field task. It then deletes one world,
re-evaluates all modes, and requires the fixture evaluator and independent
semantic reference to agree. The [machine-readable result](v7_leave_one_world_out_20261104.json)
records task hashes, omitted and retained case IDs, and newly accepted modes.

| Family | Worlds | C1 omissions admitting an insecure mode | C3 omissions making a mode feasible |
| --- | ---: | ---: | ---: |
| CSRF origin | 3 | 3 | 2 |
| Deserialization allowlist | 3 | 2 | 2 |
| Environment injection | 3 | 2 | 2 |
| KDF salt | 2 | 1 | 1 |
| Key rotation | 3 | 2 | 2 |
| Nonce uniqueness | 3 | 2 | 2 |
| Signature algorithm | 3 | 2 | 2 |
| TLS hostname | 3 | 2 | 2 |
| **Total** | **23 deletion opportunities per condition** | **16/23** | **15/23** |

All eight families had at least one deletion that changed the checker result.
Of the 16 newly accepted C1 modes, **8 would wrongly allow a forbidden case**
in the full task, **7 would deny a legitimate case**, and **1 would return the
wrong salt**. These categories are based on the omitted full-task worlds, not
on a security judgment about deployed code.
For example, removing `cross_site_request` from the CSRF task made
`token_only` pass the remaining C1 worlds even though the full reference
rejects it. Removing `replay` from the nonce task made `accept_any` pass.
Removing `principal_b` from KDF made a fixed salt pass the reduced C1 test.
In the C3 condition, the full worlds admit no mode; 15 of 23 single-world
deletions made at least one mode satisfy the **reduced** world set. This
does not mean the original C3 task became solvable: the deleted security
case remains part of its stated requirement.

These are sensitivity counts for a deliberately small authored test suite.
They are not failure rates for sampled benchmarks, model behavior, or real
security. Deleting a legitimate positive case can also admit `reject_all`,
which is a functional failure rather than an unsafe acceptance. The result
shows why a missing case or a weak raw test can change apparent success and
why the full task semantics must be reviewed independently.

Reproduce from the repository root:

```sh
python3 -B -m analysis.v7_leave_one_world_out_20261104 --check
python3 -B -m unittest -q tests.test_v7_leave_one_world_out_20261104
```
