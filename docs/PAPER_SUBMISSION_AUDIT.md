# Paper submission audit — 3 October 2026

**Artifact reviewed:** `paper/final.md` and derived PDF/DOCX, built from the completed exploratory cohort. **Verdict:** complete manuscript suitable for mentor review or submission as a clearly labeled exploratory report, once author names and affiliation are supplied. It must not be presented as a confirmatory or validated secure code benchmark study. A particular journal or conference style file has not been specified.

## Dataset and traceability

| Check | Finding |
| --- | --- |
| Frozen study source commit | `98a4dcf414672c1725e4acdb9f08045370aa7f64` in main manifest. Paper analysis added after collection. |
| Main denominator | 40 indexed episodes: five families × four condition cards × guidance on/off × one run. All 40 archived logs and receipts pass current integrity checks. |
| Pilot denominator | Eight disjoint AEAD episodes. All eight pass current artifact integrity checks; they are never pooled into main estimates. |
| Historical records | 101 receipts inventoried across incompatible cohorts; 87 pass the current validator. Older smokes, superseded pilot, and containment simulation are excluded from main estimates. |
| Raw source preservation | Original raw files remain unmodified. Analysis records per-file hashes and checks them again before writing derived output. Raw paths are Git ignored pending reviewed release. |
| Analysis outputs | `paper/artifacts/results.json`, run CSV, factor summaries, family contrasts, historical inventory, source API inventory, and input hashes. Six figures are generated from these outputs. |
| Numerical consistency | Manuscript anchors `40`, `8`, `16/20`, `9/20`, `24/28`, `17/25`, `15/20/5`, and `0/81` are present in derived records. Builder refuses a stale main data summary. |
| Article format | Approximately 6,900 source words including references, 248-word abstract, 22 numbered references with direct primary links, six figures with captions, three tables, data availability and ethics sections. PDF text extraction confirms key sections and values. |
| Repository tests | `python3 -B -m unittest discover -s tests -q` passed **164 tests** in 67.427 seconds with Docker daemon access on 3 October 2026. An initial run while Docker was off failed only the three Docker-dependent catalog tests; rerunning after Docker became available passed all 164. No main experiment was relaunched. |
| Re-render | `paper.build_submission` generated the 16-page PDF, DOCX, and all six PNG figures. Table captions and tables were checked on the same PDF pages. `git diff --check` passed; the derived data hashes matched across two identical analysis runs. The official Docker safety gate separately passed all eleven checks on 3 October 2026; its local receipt was not used to alter historical study results. |

## Reviewer 1 — ML and experimental design

The earlier protocol specifies falsifiable hypotheses and GEE on family clusters. The actual main has only five clusters and one observation per factorial arm. No genuine strategy outcome was independently coded. The manuscript **does not** run GEE, calculate p values, or treat 136 actions as independent observations. The five family bootstrap intervals are labeled descriptive sensitivity checks. Planned confirmatory claims, interactions, and statistical power are explicitly unresolved. Residual problem: five selected families and fixed block order cannot identify a population effect of guidance or feedback; this requires new data.

## Reviewer 2 — cybersecurity and benchmark validity

The paper audits the exact executable evaluator and finds the nominally unavailable cells use `passed = candidate_passed and condition_reachable`. Nine episodes demonstrate raw family pass with policy rejection. The manuscript names this a hidden acceptance veto and refuses to infer rational stopping. Its SQL injection, XSS, nonce, key derivation, and AEAD examples reveal limited or faulty security tests; it reports **finite check acceptance** throughout. The candidate and evaluator share a Python container interpreter, so the oracle is not adversarially independent. Residual problem: repairable and genuinely impossible tasks need new executable validation, truthful feedback, and stronger security properties before benchmark claims can be upgraded.

## Reviewer 3 — strongest skeptical objection

The strongest objection is construct failure: the intended phenomenon, choosing when to stop on truly unrecoverable security work, is not actually instantiated by the current `U` tasks. The corresponding core hypothesis cannot be tested. The manuscript treats this as a principal finding of a measurement audit and narrows the conclusion to observable actions and benchmark behavior. A second objection is the narrow test suite: 16 accepted candidates may be insecure. A third is that guidance and feedback contrasts are based on one local small model and five task families. None are resolved by stylistic edits; the manuscript documents them and specifies required next experiments.

The revised paper foregrounds the **9/20 test–gate discordance** and labels it a post collection audit metric. Its title and conclusion describe a property of this evaluator. They do not claim the hidden veto caused any particular agent action. Section 8.3 states a falsifiable future test of feedback opacity versus agent stopping behavior.

An additional receipt audit found that all 81 per-action check records omit the raw family-test outcome. Only final receipts expose it. The article therefore does not claim that a later revision followed an already passing raw check; the terminal nine cases and the post-failure resubmission counts are separate observations.

A read-only hash search of auxiliary Docker logs found possible matches for 37 of the 81 action checks; 44 had no matching sidecar, and every matched hash appeared in more than one sidecar. These auxiliary files are not the frozen, uniquely run-linked action receipts. They are therefore not used to reconstruct an action-level raw-pass timeline or to strengthen the stopping claim.

## Reviewer 4 — reproducibility

The local analysis verifies saved receipts, logs, schedule hash, and archive file hashes, and the renderer regenerates figures, PDF, and DOCX without executing candidate code. Tested source commands and versions are in `paper/README.md`. Limitations: raw trajectories are not included in Git, the exact Ollama binary/model weights digests were not frozen, the font path is macOS specific, two final logged source hashes differ from executed code, and 14/77 logged submissions do not parse (11 contain a redaction marker; three have no identified cause). A third party with only the public repository can inspect derived data but cannot fully reproduce the analysis from raw input. This is stated in the article and README rather than silently claiming full independent reproducibility.

## Conclusions challenged and retained

| Potential false explanation | Test performed on saved artifacts | Finding |
| --- | --- | --- |
| Task difficulty explains the guidance contrast | Stratified by five families; inspected per-family acceptance and leave-one-family-out estimates. | Only key derivation and SQL injection show on/off differences; data do not resolve difficulty or order. |
| Timeout masquerades as repair failure | Crossed terminal stop and candidate acceptance receipts. | One repairable episode had an accepted candidate and a terminal timeout. Reported separately. |
| Actions imply strategy changes | AST and called API inventory calculated only for 25 parseable adjacent pairs; inspected five examples. | 17 API inventories changed, but strategy transition remains unmeasured. |
| Apparent false success comes from claim parser | Compared raw and conservative public claim recovery. | Raw field is 40/40 unknown; 15 recovered success statements had finite checker support, five remain unknown. |
| Unavailable tasks were truly impossible | Inspected Docker candidate decision path and raw evaluator receipts. | Hidden veto explains nine raw passes; actual impossibility was not established. |
| Verifier proves software security | Compared implemented test strings with the claimed properties and NIST guidance where applicable. | Sparse tests and an AEAD pilot negative test defect preclude this claim. |
| Repeated actions inflate statistical confidence | Summaries computed per episode; uncertainty resampled only whole family clusters. | No action-level pseudoreplication or confirmatory significance statement. |

## Required human finishing items

1. Insert exact author names, affiliations, email/contact, acknowledgments, and funding/ethics statements only if verified by the research team.
2. Select the target venue or course template and apply its formatting, length, and disclosure requirements. The PDF is a clean neutral A4 manuscript, not an assumed publisher template.
3. Decide whether the reviewed raw archive can be released and, if so, publish it with checksums, licensing, privacy review, and matching analysis commit. Until then, describe raw availability accurately.
4. If the goal is a confirmatory paper on rational stopping or RAG effects, redesign the unavailable task mechanism and verifier, then collect a new, repeated dataset under a new protocol. Do not reinterpret these exploratory runs as that dataset.
