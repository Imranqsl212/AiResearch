# Excluded cross-model RAG pilot: descriptive audit

This report is generated from the two saved nine-slot receipts and raw episode logs by `python3 -m analysis.report_cross_model_rag_excluded`. All 18 episodes are excluded from main analysis.

- Qwen: `qwen3:4b` digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`; 9/9 valid; 40 recorded provider requests. Schedule SHA-256 `5ccd31362ef8a16a77eaf19e96f691c0b188171283e78fda8c278efe9dcfacb2`; receipt file SHA-256 `91abee7dff0e7d2af9a274ce9cdbf9142a1b1306f78a247052cba3b86353f214`.
- Gemma: `gemma3:4b` digest `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`; 9/9 valid; 13 recorded provider requests. Schedule SHA-256 `f840b934c63fa827bde6bd3b50058467b78308c0c54ce4a4329541fd28b4b20b`; receipt file SHA-256 `9a5c291d8ea658daca324d8e6b0569cdd3d5532b4766b8a541503bc7bbd3a09c`.
- The fixed seed (11), temperature (0.3), order, six-action budget, 256-token output cap, `num_ctx=8192`, request/episode timeouts, retrieval manifest, corpus hash and delivered document IDs match across models. All 9 first provider JSON requests are identical after deleting only the top-level `model` field. R0/R1/R2 initial input lengths are not equal.
- Qwen's 13-file source archive was reverse-patched and assembled **after** its run. Gemma's 13-file archive index predates its first event. Both archives byte-match their own scheduled source hashes. The four changed source files prevent treating these as a frozen cross-model replication.

| Cell | Input chars | Qwen actions / submissions / secure pass / stop | Gemma actions / submissions / secure pass / stop |
| --- | ---: | --- | --- |
| C1/R0 | 2713 | INSPECT,SUBMIT,INSPECT,SUBMIT,INSPECT,TERMINATE; 2 submissions; 0 secure pass; VOLUNTARY (0 left) | TERMINATE; 0 submissions; 0 secure pass; VOLUNTARY (5 left) |
| C1/R1 | 3439 | INSPECT,INSPECT,SUBMIT; 1 submission; 1 secure pass; CHECKER_PASS (3 left) | TERMINATE; 0 submissions; 0 secure pass; VOLUNTARY (5 left) |
| C1/R2 | 3437 | INSPECT,INSPECT,SUBMIT,INSPECT,SUBMIT,TERMINATE; 2 submissions; 0 secure pass; VOLUNTARY (0 left) | TERMINATE; 0 submissions; 0 secure pass; VOLUNTARY (5 left) |
| C2/R0 | 2848 | INSPECT,SUBMIT; 1 submission; 1 secure pass; CHECKER_PASS (4 left) | INSPECT,SUBMIT,TERMINATE; 1 submission; 0 secure pass; VOLUNTARY (3 left) |
| C2/R1 | 3574 | INSPECT,INSPECT,SUBMIT; 1 submission; 1 secure pass; CHECKER_PASS (3 left) | INSPECT,TERMINATE; 0 submissions; 0 secure pass; VOLUNTARY (4 left) |
| C2/R2 | 3572 | INSPECT,INSPECT,SUBMIT; 1 submission; 1 secure pass; CHECKER_PASS (3 left) | INSPECT,TERMINATE; 0 submissions; 0 secure pass; VOLUNTARY (4 left) |
| C4/R0 | 3064 | INSPECT,INSPECT,SUBMIT,INSPECT,SUBMIT,TERMINATE; 2 submissions; 0 secure pass; VOLUNTARY (0 left) | TERMINATE; 0 submissions; 0 secure pass; VOLUNTARY (5 left) |
| C4/R1 | 3790 | INSPECT,SUBMIT,INSPECT,SUBMIT,TERMINATE; 2 submissions; 0 secure pass; VOLUNTARY (1 left) | TERMINATE; 0 submissions; 0 secure pass; VOLUNTARY (5 left) |
| C4/R2 | 3788 | INSPECT,INSPECT,SUBMIT,INSPECT,SUBMIT,TERMINATE; 2 submissions; 0 secure pass; VOLUNTARY (0 left) | TERMINATE; 0 submissions; 0 secure pass; VOLUNTARY (5 left) |

## Interpretation and limits

Qwen has secure checker passes in C1/R1 and all three C2 cells. Gemma has no secure checker pass in these nine cells. The blocks have one episode per model and cell within one finite authorization family. They support only these observed trajectories; they do not estimate model performance, a RAG effect, a population rate, or statistical significance.

Gemma terminates on its first action in every C1 and C4 cell. Its C4 voluntary stop after public proof with budget left satisfies only the operational stop indicator. The identical immediate C1 pattern means this is **not** evidence that Gemma recognized the impossibility proof. Strategy and proof recognition were not independently coded.

Retrieved documents were delivered in R1/R2 first prompts, but recorded document use is unknown. The full first provider request is archived per slot and its hash was recomputed. Later request options and request hashes were logged before dispatch; later full request bodies were not saved, so their hashes cannot be independently recomputed.

## Source and archive provenance

- Qwen archive: `/Users/imranmzakirov/Desktop/research/experiments/runs/v1_rag_matched_seed11_20261004_source_provenance/source_snapshot_recovered`; `post_run_source_snapshot_recovery`; index SHA-256 `1118f83ece7f042e28079c6d5e993b29d54583d9e4ca7b7a14fd777489abe5bd`.
- Gemma archive: `/Users/imranmzakirov/Desktop/research/experiments/runs/v1_rag_gemma3_4b_seed11_20261004_source_provenance/source_snapshot`; `pre_run_source_snapshot`; index SHA-256 `5792e03c51cf35a92e72550404837fefd02ad2280480da05cf74345b51f7f501`.
- Scheduled source SHA-256 differs in four files:
  - `agent/finite_candidate_contract.py`: Qwen `f821ee5ef7d10074ec8e13ffd044dbc05a02b46f903d18debf8857e892e9748e`, Gemma `27310ace929a5b4e6212cfc607221b6fe89e16d15a6e2f30b77ad302518c6948`.
  - `agent/v1_ollama_adapter.py`: Qwen `e9ede1f1464729bf4ab11a506206d8df91e506f03afd0ae1a1b31829b60ee9d7`, Gemma `0dde9844b5afcf0b1962da083fc55a2a31778a31180620a8bd31dfc964db74f7`.
  - `benchmark/finite_family_registry.py`: Qwen `e29a68de7526c5fd765e8694f727d867f47406bb2bb9551a4d6421ef6047b400`, Gemma `e5494a819d47011da8c4b62efdad6043bb3ff1a5c12c93499785e7c30e9aede7`.
  - `experiments/v1_collector.py`: Qwen `ae99be59056a50704eba60e9020fa81d8e0267dff9f846f1bbd53f193a345029`, Gemma `bbb98ed9c6e24cd3cda9b2d73ed0405bb1573e33f442d601d627462f4c0b4795`.

The machine-readable JSON contains every cell's ordered actions, submissions, stop reason, remaining budget, retrieved document IDs, normalized first-request hash, block hashes and archive evidence. Qwen's later source drift causes the original runner's `verify-run` source freeze check to fail. Gemma's `verify-run` passed immediately after collection. This offline audit checks each saved archive against its own schedule and replays each episode's proof and candidate receipts.
