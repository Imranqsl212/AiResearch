# Independent admission packet for the proposed v7 catalog

**Status: PENDING, not main admitted.** This packet points reviewers to an
alternative 20-family catalog: the unchanged original four families and
batches A/B, plus the **separate v7 batch C**. Its batch-C
[`index.json`](../benchmark/tasks/v7_batch_c/index.json) has SHA-256
`f8fac1b0171152237f2736493b286ef7cca1e853fa1880915a7c2484817c54d1`.
The existing [v6 review forms](HUMAN_ADMISSION_REVIEW_PACKET_20261005.md)
refer to the old batch-C artifacts and cannot be transferred to v7.

Use the [v7 two-reviewer register](human_admission_review_register_v7_candidate_20261005.csv)
and [v7 adjudication register](human_admission_adjudication_register_v7_candidate_20261005.csv).
Both are blank: **40 pending reviewer rows, 20 pending adjudications, zero
admitted families**. The checker binds each completed row to the exact task,
proof, evaluator and independent-reference files in the selected v7 index;
it does not authenticate a person or grant scientific admission:

```sh
python3 -B -m analysis.validate_human_admission_register --catalog v7-candidate
```

For each family, reviewers should inspect C1–C5 task/proof bytes, public
projection, all finite worlds, weak/strong/oracle behavior, C3/C4
same-observation witness, C5 false rejection, hidden-label leakage, and
external validity. Each must record their own identity, conflict status,
source commit and evidence. An adjudicator records the final disposition
after two independent reviews. The review cannot be signed against the
current dirty working tree; a later clean source commit must preserve the
exact reviewed bytes.

The [adversarial v7 audit](BATCH_C_V7_SEMANTIC_CANDIDATE_20261005.md#remaining-admission-questions)
gives specific items requiring judgment: seven `reject_all` modes violate
legitimate-request availability but do not admit attacks; eight C1 modes
unsafe-accept and three KDF modes emit wrong outputs. The C3/C4 proof is
about full required-output conformance under a bounded stateless language.
Reviewers must decide whether that is the desired construct, whether the
RSA/Ed25519, shared-record KDF and deserialization worlds are coherent, and
whether mode labels reveal the intended answer. An
[excluded fake-provider integration](BATCH_C_V7_EXCLUDED_INTEGRATION_20261005.md)
checks software routing only.

No review row in either register has been filled by an automated validator.
The main schedule and R1 corpus still reference older, unadmitted versions;
finishing this form alone does not open the main gate.
