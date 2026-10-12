# R1 v0.2 independent source review packet — 5 October 2026

**Status: `PENDING_HUMAN_REVIEW / EXCLUDED_PROTOTYPE_UNREVIEWED`.** This packet is for the [R1 v0.2 candidate](R1_TWENTY_CANDIDATE_V2_20261005.md) only. The earlier [v0.1 review register](R1_TWENTY_REVIEW_REGISTER_20261005.csv) and its 40-slot excluded live pilot are separate; no v0.2 model run or main-study R1 admission has occurred.

The [two-reviewer register](R1_V2_SOURCE_REVIEW_REGISTER_20261005.csv) has **40 pending rows** (A/B for each of 20 paragraphs). The [adjudication register](R1_V2_SOURCE_ADJUDICATION_REGISTER_20261005.csv) has **20 pending rows**. Names, findings, attestations, and final decisions are blank. Every row binds the retrieval version, family, document ID and SHA-256, public-card projection hash, corpus SHA-256, candidate manifest file SHA-256, snapshot manifest digest, and the **exact cited URL/body SHA-256 pairs**. The corresponding `source_body_files` are relative to the historically named private archive `experiments/runs/r1_source_snapshots_candidate_v2_20261005/`, now tracked in this local Git branch. Two paragraphs cite two URLs, so the forms bind 22 page bodies in all. Within the pipe-separated URL, body-hash, and file columns, positions correspond exactly.

| Frozen evidence | SHA-256 |
| --- | --- |
| [v0.2 corpus](../benchmark/retrieval_corpus_r1_20_candidate_v2.jsonl), file bytes | `01b24e29b1c938abfb80e6bceaa5e0b6a0f55c130191cf3e2f4031e4f6d61894` |
| [v0.2 candidate manifest](../benchmark/retrieval_manifest_r1_20_candidate_v2.json), file bytes | `10f345f98698c814ba0b5672ce1063ca134375b8815f9e4edd951d4953dc4ad3` |
| [private snapshot manifest](R1_V2_PRIVATE_SOURCE_SNAPSHOTS_20261005.md), canonical content | `1c1a931ef7176364edc202d8cf3d975966f0c378f89796ba8f2778bf2dd23041` |

The cited Stripe page's tracked `snapshots/03.body` is a [redacted release copy](R1_V2_PUBLICATION_REDACTION_20261012.md). Its SHA-256 in the registers identifies those transformed bytes; the original HTTP-response SHA-256 and local private preservation are recorded separately. The other 21 snapshot bodies remain unmodified. Reviewers must account for this transformation when assessing that page; the mechanical validator proves register-to-file consistency, not equality of the redacted file to the original HTTP response.

## Reviewer procedure

Assign two independent people with relevant source and task expertise. Each reviews the delivered paragraph, **every** cited frozen response body, the C1–C5 public card, finite candidate modes, task reference/proof, and the exposure that an R1 agent would actually see. Record the exact page section or evidence for each cited URL in `source_evidence`, using ` | ` to separate the two sources when present. In `task_evidence`, point to the public card/modes and concrete example or reference location supporting the relevance and leakage judgment. Complete each row before viewing the other reviewer's findings. The reviewer supplies a real name, expertise, conflict declaration (`NONE` if none), date, notes, and personal attestation; a validator cannot authenticate them.

Record `PASS`, `FAIL`, or `UNCERTAIN` for source support and task relevance. Record `NO_LEAK`, `LEAK`, or `UNCERTAIN` for hidden fact/reference leakage, and `ACCEPTABLE`, `TOO_DIRECT`, or `UNCERTAIN` for answer cues from public finite mode names. These are distinct questions: a paragraph can accurately paraphrase an official page yet make the intended finite action too obvious. `KEEP` requires both `PASS` values, `NO_LEAK`, `ACCEPTABLE`, and no disclosed conflict. Otherwise choose `REWRITE` or `REJECT` with a reason. Unfinished fields stay `PENDING`.

Review the seven repaired paragraphs with the [v0.2 repair notes](R1_TWENTY_CANDIDATE_V2_20261005.md) in mind. For the unchanged paragraphs, examine the answer-cue questions from the earlier [spotcheck](R1_SOURCE_SUPPORT_SPOTCHECK_20261005.md), especially webhook body verification, upload content, and SSRF destination checks. The spotcheck is background, **not** either blind v0.2 reviewer. The NIST snapshots contain publication landing pages, not the linked final PDFs; if that is inadequate to support a claim, record `UNCERTAIN` or a failure and preserve any additionally reviewed PDF under a new explicit version binding before `KEEP`. RFC `#section-3.1` is a citation fragment; the frozen HTTP body covers the full page.

After both rows are complete, a third person fills the adjudication row. Copy the two reviewer dispositions, explain disagreements (or write `NONE` if they agree), and record a reason, evidence, conflict declaration, date, and attestation. Final `KEEP` requires **two independent `KEEP` reviews** of this exact version and no disclosed adjudicator conflict. A rewrite changes the paragraph identity: create a new corpus/version, source binding, and review packet; do not silently carry these forms to revised bytes.

## Mechanical check and limit

```sh
python3 -B -m analysis.validate_r1_v2_source_review
python3 -B -m unittest tests.test_validate_r1_v2_source_review -v
```

The [validator](../analysis/validate_r1_v2_source_review.py) verifies the 22-body archive, exact file/version/URL/body bindings, complete 40/20 row inventory, decision tokens, evidence fields, distinct reviewer identities, and consistency of final `KEEP` with two positive reviews. For untouched forms it reports 40 pending reviews, 20 pending adjudications, and zero recorded `KEEP` families. It **always** reports `human_review_verified=false`, `r1_admitted=false`, and `main_ready=false`: source accuracy, independent judgment, semantic leakage, and permission to run the main study require human and study governance decisions. The snapshot files are tracked in the local Git branch; this packet does not certify them as suitable journal supplements.
