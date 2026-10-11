# Excluded full-catalog live feasibility block — 5 October 2026

**Status:** complete; `phase=pilot`, `eligible_for_main_analysis=false`. This is an
engineering measurement of whether the local agent can produce its own
oracle-secure candidate in the finite tasks. It is not a prospective main
effect estimate or a journal confirmatory result.

## Frozen execution and audit

The [schedule](../experiments/runs/full_catalog_live_feasibility_20261005/schedule.json)
reserved exactly one C1 and one C2 slot for each of 20 families, randomized
before model dispatch. Every slot was attempted once, with no replacements.
The model was `qwen3:4b`, local Ollama digest
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`,
R0 retrieval, temperature 0.3, at most six decisions, a 180-second episode
budget, a 90-second provider-request timeout, 256 predicted tokens, and a 4096
token context window. The schedule SHA-256 is
`db498edab9f4665455a6a5c5da76501159d6f7ab36c99aeb7a4ee137195e0592`.
Its source archive contains the exact 241 indexed files with matching SHA-256
digests.

The [run receipt](../experiments/runs/full_catalog_live_feasibility_20261005/run.receipt.json)
has SHA-256
`36f91eda1ffeeb07f9c7f705ca128158f913d39e674e750db359f6adbaed556c`.
All 40 slot-result files match that receipt. The 39 episodes with a saved
manifest, including nine invalidated episodes, were reloaded with
`analysis.v1_pipeline.load_episode` without integrity errors. Slot 9 has a
reservation, request archive, prompt, schedule, and log, but no completed
manifest; its separate slot-result receipt remains INVALIDATED. It must not be
reconstructed as a successful episode after the fact.

## Observed outcomes

| Measure | Count |
| --- | ---: |
| Prescheduled slots | 40 |
| Valid excluded episodes | 30 |
| Invalidated slots | 10 |
| Valid episodes with an agent-generated oracle-secure submission | 14 |
| Distinct families with such a submission | 10 of 20 |
| C1: valid / secure onset | 14 / 4 |
| C2: valid / secure onset | 16 / 10 |
| Valid episodes ending in checker PASS / voluntary stop / decision budget | 14 / 6 / 10 |

The 14 validated onsets were slots 6, 17, 18, 19, 21, 24, 25, 27, 28, 29,
32, 38, 39, and 40. They span environment injection, deserialization
allowlists, nonce uniqueness, path boundaries, counter races, salt generation,
signature algorithms, DNS rebinding, authorization, and ambiguous parameter
handling. The first secure submission appeared at decision 2 in 12 episodes
and decision 4 in two episodes. These are observed agent actions, not the
authored reference candidates replayed by the earlier 100-slot rehearsal.
Only 13 families have valid episodes in **both** C1 and C2: four reached a
secure onset in both, three in C2 only, and six in neither. Seven family pairs
are incomplete due to invalidated slots. This paired table is descriptive;
the pilot did not repeat cells or establish a condition effect.

Nine slots experienced a local Ollama request timeout, identifiable by the
same redacted error-message SHA-256. Eight retained an invalidated manifest;
slot 9 also hit a five-second Git-status timeout while writing its manifest,
so the runner recorded an invalidated slot without a manifest. Slot 23 ended
`ERROR` after a parsed response failed the bounded candidate-shape protocol.
The ten failures remain in the denominator and were not replaced. Because
the missing outcomes are material, 14/30 is only the fraction **among valid
episodes**; it must not be presented as the success probability of all 40
assigned slots. The extreme all-slot range is 14/40 to 24/40 if every
invalidated slot is assigned failure or success, respectively.

## Interpretation and next gates

The block establishes that the local model can reach a genuine secure onset
for a subset of the finite families, allowing a matched C5 continuation
feasibility probe. It also reveals a substantial timeout/missingness problem
for the current runtime budget. A later protocol must preserve all assigned
slots and predeclare how it handles timeouts; it cannot silently keep only
successful onsets. The C1/C2 counts are descriptive: the tasks and feedback
states differ, and one episode per cell with invalidations cannot identify a
causal condition effect.

No observation in this block is main eligible. Independent human benchmark
admission, an implemented and frozen prospective schedule, source/runtime
binding, R1 review, a stable provider budget, and the separately specified
C5 matching design remain necessary before the project can claim READY for
a confirmatory paper.
