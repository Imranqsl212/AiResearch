# Local original-byte archive audit — rechecked 16 October 2026

**Result: `LOCAL_ARCHIVE_LINK_VERIFIED_REVIEW_ONLY`.** The original archive,
named as a private review copy when created but now tracked on GitHub, is
present. An independent, read-only verifier checked its exact bytes
against the previously recorded frozen SHA-256, its sidecar receipt,
and the original-byte claims in the sanitized archive manifest. It does not
import the sanitizer, the paper analysis pipeline, or the transformed-data
recount. Neither archive nor either receipt was modified.

| Frozen artifact | SHA-256 verified from local bytes |
| --- | --- |
| Original archive (legacy private filename) | `39ded8a4301ba0ebb193b48d71b032b0127a521c381fa378c67d08132319fc26` |
| Sanitized review archive | `48720a5620a1437094268452caab8f0168516454166147e575dea1c1039c0dd3` |
| Sanitization manifest inside the review archive | `a53a24fedc8f0a9f4fce2bf7d4451ebcb62cd06fc8de1d3b8ae465fc74dffef7` |

The verifier checked all **313** original archive members against the
sanitization manifest's original hashes and sizes. It also checked the **312**
non-inventory source members against the private inventory, and checked all
**312** corresponding sanitized members against their transformed hashes and
sizes. Exactly **200** member byte strings changed and **112** remained
identical. The original inventory was replaced by the sanitization manifest;
the sanitized archive also adds a review notice. Both sidecar receipts and
both archive status flags remain consistent with a review-only package.

The verifier separately read the original main result index and terminal
receipts, checked all 40 original log hashes, and recomputed **40 main
episodes**, **20** nominally unavailable, **25** raw family-test passes,
**16** final candidate acceptances, and **9/20** unavailable episodes with
raw-test pass followed by final rejection. The four condition arms each have
ten episodes. Repeating the same narrow count on the sanitized records gave
the same totals. Thus the current tracked input ledger's version drift does
not alter this archived 9/20 terminal-receipt count.

## Separate input-ledger version boundary

The original inventory records the SHA-256 of the input ledger used when the
original package was built, but that exact CSV was not stored as a member of
the archive. The **current** tracked `paper/artifacts/input_hashes.csv` has a
different SHA-256. Of its 311 input entries, **308** still match the archived
inventory; the three differing digests are for `analysis/paper_pipeline.py`,
`docs/OVERNIGHT_PROFILE.md`, and `experiments/executable_episode.py`. The
inventory has one additional package notice outside the 311 inputs. This
drift reflects later workspace versions, including the 16 October path
portability fix in `analysis/paper_pipeline.py`; the archived source members
and their mapping still verify. The
original CSV byte sequence cannot be reconstructed or independently verified
from the inventory digest alone, so this audit makes no claim that the current
CSV is the exact historical packaging ledger.

## Scope and reproduction

```sh
python3 -B -m paper.audit_original_archive_provenance
python3 -B -m unittest -q paper.test_audit_original_archive_provenance
```

The audit reads tar members in memory without extracting or printing archived
content. It verifies a **local archive-to-archive byte link and the stated
terminal counts**. It cannot establish an external timestamp or chain of
custody, rerun the original model/evaluator, prove the task oracle was fair,
or establish real-world code safety. It is not a privacy review and does not
approve journal upload of either archive. The original archive and the
sanitized candidate are tracked in public GitHub data revision
`37074c198237ade67eb76921333b2835d329c863`; that fact
does not change the audit's `REVIEW_ONLY` verdict.
