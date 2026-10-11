# Independent task admission packet — prospective v1

**Status: awaiting independent review.** This packet makes the missing human gate actionable. The machine admission report covers 20 finite families and 100 C1–C5 artifacts, but its `human_admission_review` field remains `MISSING`. No row below is approved by the authors' code or by this packet.

The blank [two-reviewer register](human_admission_review_register_20261005.csv)
has 40 rows (20 families × reviewers A/B) and `PENDING` in all seven criteria.
It is a form for actual reviewers, not evidence of approval.
The separate [adjudication register](human_admission_adjudication_register_20261005.csv)
has one blank final-decision row per family. All 20 final decisions are
`PENDING`.

## Reviewer assignment and evidence

Use two independent reviewers with relevant software-security or formal-methods experience. Each reviewer should inspect the task, proof, evaluator, separate reference, public projection, and saved challenge/mutation record **before** seeing the other reviewer's decisions. The task indexes under `benchmark/tasks/` bind the exact task and proof hashes. The machine report is `analysis/admission_review_20261004.json`; the batch-C precheck and its limits are in `docs/benchmark_admission_precheck_20261004.md`.

For **each family**, record `PASS`, `FAIL`, or `UNCERTAIN` for these seven criteria, with a concrete counterexample or supporting file/line when possible:

1. The repairable C1/C2/C5 action space contains at least one independently confirmed secure candidate; the starter is genuinely insecure.
2. C3/C4 impossibility follows from the stated *allowed actions and observable environment*, not a hidden condition flag or a gate that simply refuses success. Check the actual observation collision or exhaustive proof.
3. The security oracle checks the intended finite property independently of the weak evaluator and candidate implementation; false acceptance and false rejection cases are labeled correctly.
4. Strong challenges and valid insecure mutations exercise plausible alternative failures, not only one hand-picked string. Record any surviving mutation.
5. C1–C5 public task cards, tool availability, initial state, budgets, and candidate grammar are matched except for the declared intervention. C4 evidence must be truthful and verifiable; C5 false feedback must remain hidden from the agent.
6. The public task and retrieval materials do not leak the reference candidate, hidden condition, oracle internals, or exact answer. Any unavoidable clue is documented.
7. The security story is technically accurate **within the explicitly finite scope**. Identify terms that could mislead readers into thinking the artifact proves security of arbitrary executable code.

Admission rule: any `FAIL` or unresolved `UNCERTAIN` on criteria 1–6 blocks that family. Criterion 7 requires a scope correction before admission. After independent reviews, an adjudicator records disagreements and a signed final decision; do not silently change tasks after review. A substantive change requires a new artifact/version and another review. Reviewer names, dates, affiliations or expertise, conflicts, and exact source commit must be supplied by real people.

## Recording and checking decisions

Reviewers A and B fill their rows separately. Use only `PASS`, `FAIL`, or
`UNCERTAIN` for completed criteria. Set a reviewer decision to `ADMIT` only if
all seven criteria pass; otherwise use `REJECT` with evidence and a reason.
Enter `NONE` for a declared absence of conflict, or describe the conflict.
Record the exact reviewed Git commit, the paths or case IDs supporting the
judgment, and a real review date. Do not use an author-supplied placeholder
as a reviewer's identity or attestation.

After both rows are complete, a separate adjudicator records the same source
commit, both reviewer decisions, resolution of any disagreement, an evidence
path, and a signed decision receipt in the `attestation` field. A final `ADMIT`
requires two positive independent reviews of the same version and no disclosed
reviewer or adjudicator conflict. If a task or oracle must change, create and
review a new version before recording admission; retain the rejected version
and its review history.

Run the structural audit before considering any admission decision:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m analysis.validate_human_admission_register
```

For the untouched forms it reports **40 pending reviewer rows, 20 pending
adjudication rows, and zero recorded admissions**. The audit rejects missing or
duplicate rows, invalid tokens, incomplete identities/evidence, differing
source commits, one-person duplicate reviews, a final admission without
two positive reviews, and task/proof/evaluator/reference bytes that no longer
match the cited local Git commit. It always reports `main_ready=false` and
`scientific_task_admission_granted=false`: software cannot authenticate reviewer
identity, independence, expertise, the signed receipt, or the security
argument. Those remain human and governance gates.

## Family inventory and known questions

| Family | Task index | Review priority |
| --- | --- | --- |
| authorization | `benchmark/tasks/v1/index.json` | Check finite observation classes and reference independence. |
| path-boundary | `benchmark/tasks/v2_path/index.json` | Check path aliases and symlink-related impossibility scope. |
| transaction_replay | `benchmark/tasks/v3_replay/index.json` | Check temporal traces and feedback truth. |
| counter_race | `benchmark/tasks/v4_race/index.json` | Check concurrency schedule coverage and environment certificate. |
| rolling_rate_limit | `benchmark/tasks/v5_batch_a/index.json` | Check cross-worker state and rolling-window semantics. |
| ambiguous_parameters | `benchmark/tasks/v5_batch_a/index.json` | Check duplicate-parameter observation ambiguity. |
| quota_overflow | `benchmark/tasks/v5_batch_a/index.json` | Check arithmetic bounds and mutation coverage. |
| encoded_log_secret | `benchmark/tasks/v5_batch_a/index.json` | Check transformations before every log sink. |
| webhook_integrity | `benchmark/tasks/v5_batch_b/index.json` | [Mutation audit](BATCH_B_INDEPENDENCE_REVIEW_20261005.md) checks separate strong-test and oracle implementations; human semantic review remains. |
| upload_content | `benchmark/tasks/v5_batch_b/index.json` | Approved fixture is a valid minimal 1×1 PNG; forged-header payload is invalid. Review the deliberately finite upload property, not arbitrary image decoding. |
| unicode_identity | `benchmark/tasks/v5_batch_b/index.json` | Check normalization and identity equivalence. |
| dns_rebinding | `benchmark/tasks/v5_batch_b/index.json` | Check DNS timing and observable-address assumptions. |
| csrf_origin | `benchmark/tasks/v6_batch_c/index.json` | C3/C4 impossibility witness is schematic. |
| nonce_uniqueness | `benchmark/tasks/v6_batch_c/index.json` | Finite “random” mode does not prove arbitrary nonce uniqueness. |
| signature_algorithm | `benchmark/tasks/v6_batch_c/index.json` | C3/C4 impossibility witness is schematic. |
| deserialization_allowlist | `benchmark/tasks/v6_batch_c/index.json` | C3/C4 impossibility witness is schematic. |
| tls_hostname | `benchmark/tasks/v6_batch_c/index.json` | C3/C4 impossibility witness is schematic. |
| key_rotation | `benchmark/tasks/v6_batch_c/index.json` | C3/C4 impossibility witness is schematic. |
| kdf_salt | `benchmark/tasks/v6_batch_c/index.json` | Verify claimed contradiction against actual case labels; witness is schematic. |
| environment_injection | `benchmark/tasks/v6_batch_c/index.json` | C3/C4 impossibility witness is schematic. |

This is a review worklist, not a result table. The current main gate must stay closed until accepted reviews and resulting artifact versions are frozen in the prospective manifest.
