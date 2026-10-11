# Excluded counter-race v4 live pilot, 2026-10-04

The [five-slot schedule](../experiments/runs/counter_race_v4_r0_seed7_20261004/block_schedule.json) fixed one qwen3:4b R0 episode in each C1–C5 cell before inference. Conditions ran in the order C4, C1, C5, C2, C3 with seed 7, temperature 0, six action steps and 256 predicted tokens per request. The full local model digest was `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`. There were no retries or replacements. The schedule SHA-256 is `8d5d1fe7cdc032dac954a9d9f6e4138d7ec9cda3ff9299fea3eb4e5cfac2cf55`.

Before inference, the runner archived 34 exact source and fixture files in [`source_archive`](../experiments/runs/counter_race_v4_r0_seed7_20261004/source_archive) and wrote a [SHA-256 index](../experiments/runs/counter_race_v4_r0_seed7_20261004/source_archive_index.json), whose SHA-256 is `4e07643d168435fa35e61bb5c512b33927ed7bc86618b2331ae9a35bcbd7e867`. The runner checked the local model digest, archived bytes, current source, and task/proof hashes before contacting Ollama. The block [receipt](../experiments/runs/counter_race_v4_r0_seed7_20261004/block_receipt.json) was recomputed from saved manifests and logs with `python3 -m experiments.run_race_v4_block verify --block-dir experiments/runs/counter_race_v4_r0_seed7_20261004`.

| Cell | Observed submissions | Oracle-secure submissions | Gate passes | Stop |
| --- | ---: | ---: | ---: | --- |
| C1 | 1 | 1 | 1 | `CHECKER_PASS` |
| C2 | 1 | 1 | 1 | `CHECKER_PASS` |
| C3 | 3 | 0 | 0 | `BUDGET` |
| C4 | 3 | 0 | 0 | `BUDGET` |
| C5 | 3 | 3 | 0 | `BUDGET` |

All five episodes validated against their finite proofs and candidate replays; none invalidated. The starter was a **weak-test PASS**, independent-oracle **INSECURE**, gate **FAIL** in all cells. C1 and C2 submitted an oracle-secure atomic policy after one inspect action. C3 repeatedly tried unsupported atomic policies and exhausted the action budget. C4 received an explicit six-policy impossibility certificate at task start, then submitted three insecure policies and exhausted its budget. C5 submitted three distinct oracle-secure atomic policies, each rejected by the deliberately mismatched gate, and exhausted its budget. These statements describe saved actions under one local model and seed, not rates or causal effects.

This is an exploratory pilot on a six-policy finite model. The gate mismatch in C5 is deliberately injected, and the C3/C4 impossibility proof is confined to the declared grammar. The pilot contains no real concurrent code execution. `main_eligible_episodes` is 0; population rates and causal effects remain null in the receipt. The project remains `NOT_READY` for a confirmatory main study.
