# Retrieval corpus v2 — engineering provenance, 4 October 2026

This is a **new, separately versioned engineering treatment**. It leaves the v1 corpus, retriever and manifest unchanged. The v2 files are [`retrieval_corpus_v2.jsonl`](../benchmark/retrieval_corpus_v2.jsonl), [`retrieval_v2.py`](../benchmark/retrieval_v2.py), and [`retrieval_manifest_v2.json`](../benchmark/retrieval_manifest_v2.json). The corpus contains 22 rows: 12 crypto, eight web and two payments. The retriever accepts the public `payments` domain used by transaction-replay v3 while retaining R0, R1, R2, the public-query allowlist, deterministic ranking/noise, the stripped agent-visible document projection and exposure logging.

| Frozen engineering identity | SHA-256 |
| --- | --- |
| Raw corpus bytes | `635da9eaecee5c1ba8f577a129540e6edcce4067d6ac64cbb1f8d76a6d6e52e1` |
| Retrieval implementation bytes | `47518d5bd42da181a7869390ce993d9cc554f263bcb0fc9551858e4e593051b9` |
| Retrieval config | `7cc83e3426e27aa95115fa6f7c19ba3a4bef5279a774db3b40816fda1c69ceba` |
| Canonical manifest body | `9ca48f9e416489f1aa0ef2992c55d0f0566e8e26397f7232cce52b6412a4af16` |

The manifest records all 22 canonical JSON-row hashes. The five v1 review issues were resolved by changing the v2 row text or, for the path task, also changing its public family metadata. Each revised text is a close paraphrase of the linked **primary** page; it does not contain code or a task-specific answer:

| V2 row / canonical row SHA-256 | Primary source and supported topic |
| --- | --- |
| `crypto-key-management-v1` / `9bd9170b7ce2e12f1cbfe083821b3a4ecb1de2a8d545be03bbfa72fe4235d583` | [OWASP Key Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html): key lifecycle, storage and protection. Removed unsourced source-code/log clause. |
| `crypto-insecure-padding-v1` / `372d1d6aab1e19aa8e552b3fc2b842de0324fc1c6426bb1adfa7c0e5884878c1` | [RFC 5652 §6.3](https://www.rfc-editor.org/rfc/rfc5652.html#section-6.3): N-byte CMS block padding, including a full block, and unambiguous removal. Removed the unsourced validation instruction. |
| `crypto-tls-validation-v1` / `e12132fe1dedda0fd0a4ae43866664485df11264d3513abb73a7edb45c036c28` | [OWASP Transport Layer Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html): a server certificate lets a client verify the server's identity. Removed the more precise endpoint-name-check instruction, which the linked page did not directly establish. |
| `web-sqli-v1` / `eb88c23f951c74a006ba31785adf18aa39149054955d66b0be3f4ed018640dba` | [OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html): prepared statements and bound values. Removed benchmark-specific functional-success wording. |
| `web-path-boundary-v2` / `f8b7d8105b2a9fc92046ccfb48309039d9d01efc934cca813a248785f278d3c7` | [MITRE CWE-22](https://cwe.mitre.org/data/definitions/22.html): pathname input may escape an intended directory through special elements. The old row ID/family `web-path-traversal-v1` was relabeled to the current public path-boundary family; removed benchmark-specific permitted-file wording. |

Two new payments rows provide R1 top-two coverage for the public replay task:

| V2 row / canonical row SHA-256 | Primary source and supported topic |
| --- | --- |
| `payments-transaction-replay-v2` / `24e05a29b8a5a84ee238bb7630811ebaa3ee73f0453477aa7204bf9101306e37` | [OWASP Transaction Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html): server-side transaction authorization and credentials unique to each operation to prevent replay. |
| `payments-idempotency-v2` / `f965649bb36b523135fc246271caa75362a025e72a5ca540da60dfda5149e5a3` | [Stripe API Idempotent Requests](https://docs.stripe.com/api/idempotent_requests): an idempotency key identifies a retried request so that repeating it does not perform the operation twice. The corpus row gives this shared invariant and gives no instruction about the response value; the finite fixture's response contract remains its public task card. |

The other 15 rows inherit the topical source review in [`RETRIEVAL_CORPUS_REVIEW_20261004.md`](RETRIEVAL_CORPUS_REVIEW_20261004.md). Their canonical hashes are independently listed in the v2 manifest. Source URLs are references, not pinned source snapshots or section-level content hashes; an external source may change after this review.

## Deterministic fixture check

On the current exact C1 public projections, R1 first rank is `web-authorization-v1` for authorization v1, `web-path-boundary-v2` for path-boundary v2, and `payments-transaction-replay-v2` for transaction-replay v3. Replay R1 second rank is `payments-idempotency-v2`; R2 retains the first result and deterministically substitutes an opposite-domain document. R0 returns no documents for all three. The v1/v2 web R1 second ranks still contain another web family's general guidance; `same domain` is not the same as `same family`.

[`tests/test_retrieval_v2.py`](../tests/test_retrieval_v2.py) checks 22 row hashes, v1/v2 separation, R0/R1/R2 determinism on all three public tasks, treatment metadata removal from delivered documents, exact answer/hidden-label markers, and fail-closed corpus/manifest tampering. Five tests pass locally. No model was run, no main-study RAG manifest was changed, and this engineering corpus is **not** a main RAG freeze. Before confirmatory use, review full source versions and future tasks for semantic contamination, control context length, and pilot actual exposure under a frozen model and prompt.
