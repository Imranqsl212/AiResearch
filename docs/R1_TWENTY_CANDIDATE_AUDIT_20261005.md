# Twenty-family R1 coverage audit and excluded candidate — 5 October 2026

## Decision

**There is a testable top-one R1 candidate for all 20 public finite task cards, but no main-study R1 freeze.** The active [`retrieval_v1.py`](../benchmark/retrieval_v1.py) accepts only `crypto` and `web` public domains; [`retrieval_v2.py`](../benchmark/retrieval_v2.py) adds `payments`. Their public-query builders accept only two and three, respectively, of the current 20 C1 public cards. Seventeen cards have other exact domain strings. The default [`v1_collector.py`](../experiments/v1_collector.py) path still rejects R1/R2 for every family except `authorization`; a separate explicit `r1_20_candidate` opt-in now permits **excluded R0/R1 pilot episodes** across all 20. The main orchestrator still binds the v1 retrieval corpus and does not admit the candidate.

The separate [`retrieval_r1_20_candidate.py`](../benchmark/retrieval_r1_20_candidate.py) and [`retrieval_corpus_r1_20_candidate.jsonl`](../benchmark/retrieval_corpus_r1_20_candidate.jsonl) are **excluded engineering artifacts**. They reuse ten unchanged source paragraphs from the versioned v2 corpus and add ten short, conservatively paraphrased paragraphs linked to primary pages. Every C1–C5 public projection within each family is checked for byte parity. The prototype constructs a query from public domain/objective/title/description, filters the 20-row corpus by the public domain and ranks by lexical overlap. R1 returns the first positive-score document; R0 constructs the same query and returns none. No hidden condition, proof, task facts or candidate reference enters selection. In the current catalog, all 20 R1 first ranks are their declared family document. This is curated per-family retrieval, so any eventual estimate is the effect of this particular source guidance and its added context, not the performance of an open-web search system.

| Candidate identity | SHA-256 |
| --- | --- |
| Candidate corpus bytes | `d02ba8823d3abd6879f0bbcce442fece31101effd01d994352a9e9302e94eea6` |
| Prototype implementation bytes | `c69d44424ec415e9f39ecc748f599e352cd1336ffa91fa8ba41d7c734bd34119` |
| Canonical candidate manifest body | `4ea0bbf448956ce467bca27ca34af4df977cce35f6da89edc1b24acc19833a96` |

The complete per-document and per-public-projection hashes are in [`retrieval_manifest_r1_20_candidate.json`](../benchmark/retrieval_manifest_r1_20_candidate.json). Its status is `EXCLUDED_PROTOTYPE_UNREVIEWED`. The existing v1/v2 corpus, retrieval code and experiment manifest were not changed for this candidate. The collector now has an isolated excluded opt-in; its default historical provider behavior is unchanged.

## Excluded collector integration

The opt-in requires a saved exact candidate manifest for **both** R0 and R1,
uses the candidate provider's full-public-card hash gate, and records the
corpus, manifest and provider-source file hashes. The candidate source is in
both pre-dispatch and post-run implementation inventories. R1 delivers one
source paragraph; R0 records the same public query without delivery. A pilot
requires a provider adapter that archives every request before dispatch.
Analysis independently recomputes the retrieval result and checks that the
first archived provider request contains exactly the public task and delivered
document. It refuses changed query, document, corpus, manifest or provider
source bytes, and it refuses `phase=main` for this provider.

An offline fake-provider integration test completed **40 excluded episodes**
(20 families × R0/R1) and reloaded their request archives. These are
instrumentation tests, not agent-behavior observations. The corpus remains
unreviewed, so this integration does not enable a prospective RAG comparison.
A separate [prescheduled provider-backed C2 block](R1_TWENTY_LIVE_FEASIBILITY_20261005.md)
then completed all 40 assigned slots once: 38 valid excluded episodes, two
retained protocol invalidations, and 19 complete R0/R1 family pairs. Its raw
requests and retrieved documents passed a separate replay audit. It does not
provide independent source approval or a retrieval-effect estimate.

[`R1_TWENTY_REVIEW_REGISTER_20261005.csv`](R1_TWENTY_REVIEW_REGISTER_20261005.csv) has one row per family and explicit fields for two source-support, relevance and semantic-leak judgments. Every judgment, source-page snapshot hash and disposition is `PENDING`; the register does not claim review has occurred.

## Source coverage

Ten rows inherit the exact v2 `source` and `text`: `authorization` ← `web-authorization-v1`, `path-boundary` ← `web-path-boundary-v2`, `transaction_replay` ← `payments-transaction-replay-v2`, `encoded_log_secret` ← `crypto-secret-leakage-v1`, `dns_rebinding` ← `web-ssrf-v1`, `csrf_origin` ← `web-csrf-v1`, `nonce_uniqueness` ← `crypto-nonce-v1`, `tls_hostname` ← `crypto-certificate-validation-v1`, `key_rotation` ← `crypto-key-management-v1`, and `kdf_salt` ← `crypto-key-derivation-v1`. Exact text reuse is mechanically checked against the v2 corpus SHA-256. Prior topical checks of those pages are recorded in [`RETRIEVAL_CORPUS_V2.md`](RETRIEVAL_CORPUS_V2.md). Reuse **does not** waive a new family-specific relevance or leakage review. In particular, a general CSRF-token paragraph does not address every origin-binding detail, and the finite `nonce_uniqueness` oracle is itself under scientific review.

The ten new rows have a **provisional topical check**, based on the linked primary pages on 5 October 2026. The corpus paragraphs paraphrase mechanisms, not JSON policies or exact fixture answers:

| Family | Primary page used for candidate paragraph | Remaining review concern |
| --- | --- | --- |
| `counter_race` | [MITRE CWE-362](https://cwe.mitre.org/data/definitions/362.html) | Check that the paragraph does not disclose one exact candidate mode. |
| `rolling_rate_limit` | [Redis rate-limiter documentation](https://redis.io/docs/latest/develop/use-cases/rate-limiter/) | Source is vendor documentation and may change; preserve an exact version or snapshot. |
| `ambiguous_parameters` | [OWASP WSTG parameter-pollution test](https://wstg.owasp.org/latest/4-Web_Application_Security_Testing/07-Injection/04-HTTP_Parameter_Pollution/) | Test guidance is topical, not a proof that this fixture's exact policy is realistic. |
| `quota_overflow` | [MITRE CWE-190](https://cwe.mitre.org/data/definitions/190.html) | Review the quota-specific paraphrase against the source section. |
| `webhook_integrity` | [GitHub webhook-signature guidance](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries) | Verify it gives general integrity context without handing over the fixture's exact mode. |
| `upload_content` | [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) | Filename, MIME and content language may narrow the finite options sharply. |
| `unicode_identity` | [Unicode UTS #39](https://www.unicode.org/reports/tr39/) | Pin the Unicode report version and distinguish confusable skeletons from identity rules. |
| `signature_algorithm` | [RFC 8725 §3.1](https://www.rfc-editor.org/rfc/rfc8725.html#section-3.1) | RFC addresses JWT/JWS; reviewers must judge transfer to the fixture's symbolic signature mode. |
| `deserialization_allowlist` | [OWASP Deserialization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html) | Type-control wording may make a finite mode too obvious. |
| `environment_injection` | [MITRE CWE-427](https://cwe.mitre.org/data/definitions/427.html) | Source focuses on search-path control; check fit to the fixture's broader environment contract. |

These links show where each candidate paragraph came from. None is a saved source-page snapshot, a section-level source hash, a blind reviewer judgment or an external-validity result. The code checks exact corpus bytes, public-card hashes, source host allowlist, C1–C5 public parity, document selection and absence of literal hidden markers; it **cannot** validate the paraphrase's scientific relevance or detect every semantic answer leak.

## Smallest defensible route to a frozen R1 arm

1. Complete the separate family admission review first. The 20 engineered finite mechanisms remain unadmitted; the batch-C precheck identifies a shared `complete_observation` switch in C3/C4 and a nonce/randomness construct problem. A RAG corpus cannot repair an invalid security oracle or impossibility witness.
2. Have two independent reviewers inspect **all 20 delivered paragraphs** against the exact C1–C5 public card, secure reference, candidate modes, proof and source page. Record direct source support, task relevance, any exact-answer or hidden-fact leak, and a keep/rewrite/reject decision. Resolve disagreements before main model runs. Preserve the exact reviewed page version or a permissible source snapshot for dynamic sites, and freeze a new corpus and review receipt.
3. Fix the R1 treatment definition at **one ranked document per family**, or explicitly choose another top-k before data collection. Prespecify that R1−R0 measures the total effect of the delivered excerpt **and** its context length. Record exact delivered document bytes, IDs, ranks, query, prompt/context options and usage status; delivery alone does not prove the agent used the document.
4. The offline integration and provider-backed excluded 20-family rehearsal are complete, with invalidations retained and source/code/task checks. Their frozen pilot identities are not a main freeze. Only after independent corpus and task admission should the orchestrator and main preflight bind a reviewed task, corpus, prompt, model, schedule and analysis contract.

R2 is **not ready as a controlled noise contrast** in this top-one prototype: it retains the relevant document and adds one opposite-domain paragraph, so it changes document count and context length. It may only be labeled exploratory until its target estimand and a length/position control are prespecified and the noise content receives the same review. The active v1/v2 R2 policy replaces the final rank in a top-two set; those historical outputs are a different treatment and cannot be relabeled as this candidate.

Run the excluded offline check with `PYTHONPATH=. python3 tests/test_retrieval_r1_20_candidate.py`. It covers 20/20 first ranks, R0/R1/R2 determinism, immutable corpus/manifest/public-card binding and basic leakage markers. Passing it is an engineering prerequisite, not authorization for main collection.
