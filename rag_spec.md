# Controlled retrieval specification (v1)

## Scope and status

`benchmark/retrieval_v1.py` is a separate, offline retrieval treatment for a future experiment. It does not alter the historical v0.5 fixed-guidance path in `benchmark/retrieval.py` or retroactively change earlier results. This module alone does not run agents or establish a RAG effect. The collection harness must deliver its returned public documents to the adapter, log the exposure, and retain the frozen manifest with every experiment.

The input corpus is the separate 20-row `benchmark/retrieval_corpus_v1.jsonl`, SHA-256 `8fb4dabffc9891179c91bd8419f2c5762686ba5ae307fa9b213d44ef85c2a56d`. Each row is a short paraphrase with a public URL to an official NIST, OWASP, MITRE, or IETF source. The URLs improve source traceability, but the rows lack section-level citations, source revision dates, independent quote checks, and a completed contamination review. The 20 documents cover historical catalog families; this does **not** establish that 20 benchmark task families are validated. The v1 collector currently covers one authorization family; the path and temporal fixtures are standalone and have not entered retrieval pilots. The corpus remains an engineering treatment until source review and study gates are completed.

## Frozen treatments

| Mode | Behavior | Agent-visible retrieval context |
| --- | --- | --- |
| `R0` | Construct the same public query but execute no retrieval. | No documents. |
| `R1` | Rank the controlled corpus and return the top `k` documents from the public task's domain. | Ranked documents with source labels. |
| `R2` | Keep the first `k−1` ranked documents and replace the final rank with one deterministic opposite-domain document. | Ranked documents, including the declared noise document. |

Default `k=2`, noise seed `7`. R2 preserves the first R1 document, so the treatment adds irrelevant material without removing the leading match. The opposite-domain document is selected by the lowest SHA-256 of `seed|query|document_id` among eligible records. It is not claimed to match the cognitive difficulty or token count of the displaced R1 document. The manifest freezes `k` and the seed; a changed value creates a different configuration.

The lexical ranker lowercases ASCII alphanumeric tokens in the public query and each document's domain, family, and text. Each matched query term contributes `(1 + ln((N+1)/(document_frequency+1))) × min(term_frequency,3)`. A document receives an additional fixed score of `8` when all tokens of its public family name occur in the query. Scores are rounded to eight decimals, sorted descending, then tied by document ID. R1 results are filtered to the public task's domain; R2 replaces the final same-domain result with opposite-domain noise. The ranker rejects a zero-score first same-domain result. There is no embedding model, chunk overlap, reranker, online search, or network call. Chunking is one complete corpus row per document. The algorithm and tokenizer names are versioned in the manifest. Retrieval latency is local wall-clock time and may vary between runs; rank and score are deterministic for a frozen corpus and query.

## Manifest and fail-closed validation

Call `freeze_retrieval_manifest()` before collection and save its JSON output create-once. Record `retrieval_manifest_sha256`, `corpus_sha256`, and `config_sha256` in the experiment manifest. The retrieval manifest contains every document's canonical-row SHA-256, the corpus file SHA-256, document count, module implementation SHA-256, algorithm/tokenizer/chunking versions, `top_k`, noise policy and seed, and explicit `embedding_model: null` and `reranker: null`.

The versioned engineering manifest is saved at `benchmark/retrieval_manifest_v1.json` and can be checked with `validate_retrieval_manifest`. It freezes the current corpus and retrieval implementation for engineering replay. It does not make the full study ready: corpus contamination review, model freeze, validated task expansion, and a pre-run experiment lock remain open.

Every `retrieve(...)` call recomputes and validates the manifest against the local corpus and implementation. A modified corpus, document, code file, setting, or hash raises `RetrievalIntegrityError` before any document is returned. The repository's current corpus SHA-256 is also pinned in code. A legitimate revision must be versioned and reviewed; modifying this corpus in place should not silently start a new experiment.

The query is built only from `environment.domain`, `objective.description`, `task_card.title`, and `task_card.description` in an **agent-visible task projection**. Evaluator task IDs, condition labels, expected outcomes, verifier internals, and reference solutions are not read. Corpus rows and query text with known hidden-state markers or source-like content are rejected. This is a hygiene check, not proof against all benchmark contamination; an independent review of every document and public prompt remains a pre-run gate.

## Retrieval and exposure log contract

Use `retrieve(public_task, mode=..., manifest=...)` and provide `agent_visible_documents(result)` to the agent. This public projection contains only document ID, source, and text. It strips the rank, score, content hash, and `noise_injected` treatment tag retained in the evaluator trace. After the adapter actually receives that context, place `retrieval_log_record(result, exposure_status="delivered")` in the `TASK_START` event. If delivery fails, record `not_delivered`; if it cannot be established, leave `unknown` and exclude that episode from exposure-based RAG comparisons. A retrieval result alone is not evidence of agent exposure.

The logging helper emits these fields without duplicating document text:

| Field | Meaning |
| --- | --- |
| `mode`, `retrieval_enabled`, `retrieval_version` | Frozen treatment identity. |
| `query`, `query_source`, `query_status` | Exact public query, `public_task_projection`, and `executed` or `constructed_not_executed`. |
| `retrieved_document_ids`, `retrieval_scores`, `retrieval_rank`, `retrieval_latency_ms` | Query output in rank order; R0 has empty arrays and null latency. |
| `retrieved_documents` | Per-document ID, hash, rank, score, and `noise_injected` flag. |
| `exposure_status`, `exposure_document_ids` | Delivery attestation; IDs are null if exposure is unknown. |
| `documents_used_status`, `documents_used` | `unknown` and null by default, even after delivery. Set `observed` only with an instrumented, observable use signal. |
| `corpus_sha256`, `config_sha256`, `retrieval_manifest_sha256` | Links to the frozen input and settings. |

Do not infer `documents_used` from improved performance, source edits, or mere exposure. If use is directly observed, pass the observed IDs to `retrieval_log_record(..., observed_used_document_ids=[...])`; the helper requires a unique subset of retrieved IDs. An empty list means observed non-use, distinct from unknown. The per-action trajectory should separately log any explicit retrieval tool calls if a later design allows agent-initiated queries; this v1 treatment is a single pre-task retrieval exposure.

## Analysis boundaries

RAG comparisons require matched tasks, frozen prompts/model settings and time budgets, a recorded exposure event, and an analysis plan that accounts for added context tokens. The current summaries vary in length, and R2's replacement may alter context length; token/context effects are plausible alternatives to a knowledge effect. Record the exact public payload and token usage, and preregister a length-sensitive analysis or matched-context control before confirmatory collection. These treatments do not by themselves identify learning, strategic adaptation, or security correctness.
