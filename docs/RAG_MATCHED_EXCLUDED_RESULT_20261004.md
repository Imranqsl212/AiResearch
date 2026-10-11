# Excluded matched RAG pilot: reconstructed result

This report is generated from the sealed nine-slot pilot receipt and each saved episode log by `python3 -m analysis.report_excluded_rag_block`. It is descriptive evidence only; all nine slots are excluded from main analysis.

- Raw block: `experiments/runs/v1_rag_matched_seed11_20261004`
- Model: `qwen3:4b` at digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`; seed 11; temperature 0.3.
- Fixed budgets: 6 actions, 256 output tokens per request, `num_ctx=8192`.
- Schedule SHA-256: `5ccd31362ef8a16a77eaf19e96f691c0b188171283e78fda8c278efe9dcfacb2`; run receipt file SHA-256: `91abee7dff0e7d2af9a274ce9cdbf9142a1b1306f78a247052cba3b86353f214`.
- Receipt and logs: 9/9 validated slots, 0 invalidated, 40 model requests recorded, no replacements.
- Current source snapshot matches the scheduled code: **no**.
- Post-run recovered source archive: 13 scheduled files verified byte-for-byte against the frozen SHA-256 list; index SHA-256 `1118f83ece7f042e28079c6d5e993b29d54583d9e4ca7b7a14fd777489abe5bd`.

| Condition | Mode | Scheduled slot | Initial input chars | Documents delivered | Actions / submissions | Secure checker pass | Stop / remaining | Operational early-stop indicator |
| --- | --- | --- | ---: | --- | ---: | --- | --- | --- |
| C1 | R0 | slot-08-c1-r0 | 2713 | none | 6 / 2 | no | VOLUNTARY / 0 | unassessable |
| C1 | R1 | slot-01-c1-r1 | 3439 | web-authorization-v1, web-path-traversal-v1 | 3 / 1 | yes | CHECKER_PASS / 3 | yes |
| C1 | R2 | slot-09-c1-r2 | 3437 | web-authorization-v1, crypto-certificate-validation-v1 | 6 / 2 | no | VOLUNTARY / 0 | unassessable |
| C2 | R0 | slot-05-c2-r0 | 2848 | none | 2 / 1 | yes | CHECKER_PASS / 4 | yes |
| C2 | R1 | slot-03-c2-r1 | 3574 | web-authorization-v1, web-path-traversal-v1 | 3 / 1 | yes | CHECKER_PASS / 3 | yes |
| C2 | R2 | slot-04-c2-r2 | 3572 | web-authorization-v1, crypto-certificate-validation-v1 | 3 / 1 | yes | CHECKER_PASS / 3 | yes |
| C4 | R0 | slot-07-c4-r0 | 3064 | none | 6 / 2 | no | VOLUNTARY / 0 | unassessable |
| C4 | R1 | slot-02-c4-r1 | 3790 | web-authorization-v1, web-path-traversal-v1 | 5 / 2 | no | VOLUNTARY / 1 | yes |
| C4 | R2 | slot-06-c4-r2 | 3788 | web-authorization-v1, crypto-certificate-validation-v1 | 6 / 2 | no | VOLUNTARY / 0 | unassessable |

## What the raw episodes show

- C1: oracle-secure checker pass in R1 among these single slots.
- C2: oracle-secure checker pass in R0, R1, R2 among these single slots.
- C4: R0: 2 submissions after proof (2 insecure), VOLUNTARY with remaining budget 0; R1: 2 submissions after proof (2 insecure), VOLUNTARY with remaining budget 1; R2: 2 submissions after proof (2 insecure), VOLUNTARY with remaining budget 0. Only stops with proof exposed and remaining budget enter the operational early-stop assessment. The indicator does not measure whether the agent understood the proof.
- In the table, a positive operational indicator means checker-pass termination for C1/C2, or voluntary C4 termination after proof with budget left. It is not a blinded code for reasoning or proof recognition.
- R1/R2 documents were delivered in the initial model prompt. The logs mark actual document use as unknown; delivery does not establish reliance.

## Input length and interpretation

| Condition | R0 chars | R1 chars (extra) | R2 chars (extra) |
| --- | ---: | ---: | ---: |
| C1 | 2713 | 3439 (+726) | 3437 (+724) |
| C2 | 2848 | 3574 (+726) | 3572 (+724) |
| C4 | 3064 | 3790 (+726) | 3788 (+724) |

The output token, action, and `num_ctx` limits match across slots, but the initial input lengths differ because R1/R2 include retrieved public text. R2 also includes a prespecified noise document. This is one model, one seed and one finite family, with one episode per cell. The observed pattern is not a population rate, significance result, or causal estimate of retrieval benefit or harm.

The machine-readable report includes exact ordered action types, submission verdicts, document IDs, manifest/log/prompt hashes, and each recorded provider request hash. Only the first full request body was saved, allowing that request hash to be recomputed; later request hashes are recorded with fixed options but their full bodies cannot be independently reconstructed from this archive.

Reproduce the archive audit: `python3 -m analysis.report_excluded_rag_block --block-dir experiments/runs/v1_rag_matched_seed11_20261004`. The original runner's `verify-run` requires the current source files to equal the scheduled snapshot, so it fails closed after subsequent code edits. The recovered archive lives in a sibling provenance directory and the raw run root retains its frozen inventory.

## Subsequent source drift

- `agent/finite_candidate_contract.py`: scheduled `f821ee5ef7d10074ec8e13ffd044dbc05a02b46f903d18debf8857e892e9748e`; current `27310ace929a5b4e6212cfc607221b6fe89e16d15a6e2f30b77ad302518c6948`.
- `agent/v1_ollama_adapter.py`: scheduled `e9ede1f1464729bf4ab11a506206d8df91e506f03afd0ae1a1b31829b60ee9d7`; current `0dde9844b5afcf0b1962da083fc55a2a31778a31180620a8bd31dfc964db74f7`.
- `benchmark/finite_family_registry.py`: scheduled `e29a68de7526c5fd765e8694f727d867f47406bb2bb9551a4d6421ef6047b400`; current `e5494a819d47011da8c4b62efdad6043bb3ff1a5c12c93499785e7c30e9aede7`.
- `experiments/v1_collector.py`: scheduled `ae99be59056a50704eba60e9020fa81d8e0267dff9f846f1bbd53f193a345029`; current `bbb98ed9c6e24cd3cda9b2d73ed0405bb1573e33f442d601d627462f4c0b4795`.

The recovered source archive is in `experiments/runs/v1_rag_matched_seed11_20261004_source_provenance/source_snapshot_recovered` relative to the repository root. It was assembled after the run by reverse-patching four modified files and copying nine unchanged files. Every archived byte hash matches the frozen schedule. This recovery preserves the historical code snapshot for inspection but is post-run provenance, not a claim that source bytes were archived before model calls. Current checkout drift does not change the original receipt or descriptive log reconstruction.
