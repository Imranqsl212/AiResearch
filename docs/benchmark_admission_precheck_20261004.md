# Batch-C benchmark admission precheck — 4 October 2026

**Decision: machine consistency checked; scientific admission pending.** The eight
batch-C families contain 40 saved C1–C5 tasks. The strengthened precheck compares
each saved task with the task generator, verifies index metadata and file hashes,
recomputes every saved proof, cross-checks finite truth against the separate
reference model, and compares all 160 candidate receipts. It rejects unindexed
files, missing or duplicate task rows, condition-label mismatches, public-task
differences within a family, and changes to the expected starter or feedback.

| Designed finite property | Checked result |
| --- | ---: |
| Families / condition cells | 8 / 40 |
| Candidate/condition comparisons | 160 |
| Insecure C1 modes caught by strong check | 21/21 |
| Weak raw false accepts across all cells | 127 |
| Secure C5 modes deliberately rejected by gate | 11 |

These are exhaustive counts **inside the authored policy languages**, not rates
for real software, model repairs, or independent security observations. C5 false
rejections are deliberately built into the evaluator. The C1 mutation corpus is
the set of all valid but insecure policy modes in each family, not a corpus of
independently written code mutations.

The check exposes an important admission limit: batch C represents loss of
observation with a single `complete_observation` boolean. Its C3/C4
`contradiction_witness` lists two desired decisions and labels them as sharing an
observation, but does not encode and independently verify the observation values
that make those decisions incompatible. The separate reference model also reads
that boolean. Thus the certificate validates consistency of the *declared finite
model*; it is not an independent impossibility proof for executable code. A
reviewer should inspect and, if necessary, redesign these witnesses before any
family is admitted to the main study.

The labels `nonce_uniqueness` and `kdf_salt` also need expert construct review.
For example, batch C currently treats a `random` nonce mode as secure in its
listed finite cases. That verdict does not establish uniqueness for arbitrary
random draws or an application lifetime. The intended security invariant,
challenge cases, and allowed generalization must be made explicit in the task
record before a journal claim uses that name.

Two local executable-code fixtures, SQLite injection and shell injection, have
separate Docker calibration reports. They do not turn these 20 finite families
into 20 executable-code tasks, and no model-written code repair was admitted.
Human admission review is still missing for every finite family.

Reproduce the batch-C precheck and its fail-closed tests:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m benchmark.validate_finite_batch_c_v6
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_finite_batch_c_v6 -v
```
