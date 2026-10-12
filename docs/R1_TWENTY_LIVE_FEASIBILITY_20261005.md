# Excluded 20-family C2 R0/R1 live feasibility block

**Status: completed excluded pilot; no main-eligible episodes or RAG effect
estimate.** This block exercises the unreviewed top-one
[`r1_20_candidate`](../benchmark/retrieval_r1_20_candidate.py) provider through
the real local `qwen3:4b` adapter, collector, request archive and replay
analysis. It is separate from the historical paper cohort and prospective v1
main study.

## Frozen schedule and integrity

The [schedule](../experiments/runs/r1_20_live_c2_feasibility_20261005/schedule.json)
reserved **20 C2 finite families × R0/R1 = 40 episodes** before dispatch.
Each family has one independent R0 and R1 conversation with the same task,
proof and inference seed; pair and arm execution order were randomized in the
schedule. There were no replacement episodes. The model was `qwen3:4b`,
scheduled digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`,
temperature 0.3, six decisions, 240-second episode budget, 120-second
request timeout, 256 predicted tokens and 4096 context tokens. The block
bound the exact candidate manifest, corpus, provider, task/proof rows, prompt,
collector and analysis source before dispatch. Its source archive contains 84
exact files with matching hashes.

| Artifact | SHA-256 |
| --- | --- |
| Schedule | `36701e37c0d4aaf4eee58b48a773071f34b073b2febf59ca031bb6fa6040f88d` |
| [Run receipt](../experiments/runs/r1_20_live_c2_feasibility_20261005/run.receipt.json) | `f985ad2ad4cee2427910bd4fb074da5ef41294048f7f976da520e1ac9a997f54` |
| [Post-run model-digest check](../experiments/runs/r1_20_live_c2_feasibility_20261005/model_digest_postrun.json) | `5da58b1e016cf8e99ce086ee6e133cd55e367aec39a0f16d201881d84cb754a7` |

The model digest matched at the block-start check and in a separate post-run
check. It was **not** attested in every slot; these endpoints cannot prove
that weights were unchanged at every intervening request. The post-run check
is supplemental and did not alter the original run receipt.

[`audit_r1_20_live_feasibility.py`](../analysis/audit_r1_20_live_feasibility.py)
reopens the [machine-readable audit](../analysis/r1_20_live_feasibility_audit_20261005.json)
inputs: all 40 slot reservations, result files, 40 manifests, task/proof
hashes, source archive, retrieved document records, initial provider requests
and event logs. It reruns `load_episode` to reconstruct each candidate and
public retrieval exposure. Every valid pair's first provider-request envelope
(model, decoding options and schema, excluding messages) matches across R0
and R1. R1 delivered exactly one candidate document; R0 delivered none.

## Observed outcomes

| Measure | Count |
| --- | ---: |
| Prescheduled slots / families | 40 / 20 |
| Valid excluded slots / invalidated slots | 38 / 2 |
| Families with both arms valid | 19 |
| R0 secure onsets among 19 valid R0 slots | 13 |
| R1 secure onsets among 19 valid R1 slots | 12 |
| Complete pairs: both secure / neither secure / R0 only / R1 only | 12 / 6 / 1 / 0 |
| Complete pairs with identical submitted candidate-hash sequences | 15 / 19 |

The two invalidations were **both** `transaction_replay`, one in each arm.
After `inspect`, the model returned no permitted bounded action; the saved
stop records classify them as `AGENT_PROTOCOL_NO_ACTION`. They are protocol
failures, retained in the 40 assigned slots and one incomplete family pair.
They are not counted as failed secure repair in the 19 complete-pair table.

Among the 12 pairs where both arms reached an oracle-secure submission, R1
reached it earlier in one family (`authorization`), R0 earlier in one
(`ambiguous_parameters`), and both at the same decision in ten. In
`tls_hostname`, R0 reached a secure submission and R1 did not in its single
seeded pair. These cases are descriptive, not evidence of a reliable gain or
harm from R1. The 15/19 identical candidate-hash sequences refer only to
submitted candidates; inspect actions, text and model reasoning may differ.

The first archived R1 request was **306–462 UTF-8 bytes longer** than its R0
partner in the 19 complete pairs (median 373). R1 therefore changes delivered
content **and input length**. The document was curated per family, not drawn
from an open search distribution, and its source support, task relevance and
semantic leakage have no independent human approval. Delivery does not prove
the model read or used the document. A content-specific retrieval effect needs
an approved corpus, a length-matched control, repeated seeds, and the frozen
full main schedule. This single-C2 pilot is an integration and feasibility
result only.

To recompute from the raw records now tracked in this local Git branch:

```sh
python3 -B -m analysis.audit_r1_20_live_feasibility > /tmp/r1_20_audit_recheck.json
```
