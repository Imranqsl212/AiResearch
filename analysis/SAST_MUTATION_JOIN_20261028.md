# Source-identical SAST and finite-check comparison — 28 October 2026

**Status: excluded authored calibration.** This comparison contains eight
prepared Python sources from two proposed executable-code families. It contains
zero agent submissions and zero eligible main episodes. The [derived JSON](sast_mutation_join_20261028.json)
is built by [`sast_mutation_join.py`](sast_mutation_join.py) without running a
candidate or starting Docker.

The reader joins the [Bandit 1.9.4 calibration](sast_calibration_20261025.json)
to the previously saved [SQLite](../benchmark/real_code_sqli_calibration_v3_20261004.json)
and [file-command](../benchmark/real_code_command_injection_calibration_20261004.json)
Docker calibration profiles. It verifies each exact source SHA-256 against the
current authored literal, the saved Bandit record, and the saved finite-check
profile. The existing real-code candidate validator also checks the suite and
driver hashes, case identities, and expected saved outcomes.

| Bandit result | Weak suite | Strong suite | Authored sources |
| --- | --- | --- | ---: |
| No findings | Pass | Pass | 2 secure references |
| Findings | Fail | Fail | 2 vulnerable references |
| Findings | Pass | Fail | 4 insecure mutations |

For the four prepared insecure mutations, the weak suite rejected **0/4**,
the strong suite rejected **4/4**, and Bandit reported findings for **4/4**.
The SQLite findings were B608; the file-command findings were B404 and B602.
One saved SQLite profile (`uppercase_secure_reference`) has no matching entry
in the eight-source Bandit calibration and is excluded from this table.

These are finite, authored challenge results. They do not estimate SAST
sensitivity, prove any source secure, or show how an agent repairs code. Bandit
warnings are not an oracle verdict, and disagreement with a finite suite would
require manual review. The older Bandit calibration saved parsed JSON but not
its exact stdout bytes, so that stdout hash cannot be replayed from that file
alone. The [new SAST sidecar](INDEPENDENT_SAST.md) archives raw scanner bytes
for future scans.

Recompute and verify the dated output from the repository root:

```sh
python3 -B -m analysis.sast_mutation_join --verify
python3 -B -m unittest tests.test_sast_mutation_join -q
```

This comparison does not change the benchmark gate or the prospective READY
status. A future detection-performance study needs held-out mutations,
independent human adjudication, a frozen scanner environment, and eligible
collection under the approved experiment protocol.
