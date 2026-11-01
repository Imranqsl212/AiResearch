# Prescheduled excluded v7 second wave — 1 November 2026

**Status before dispatch:** pilot only. The main gate is `NOT_READY` (12/12 checks false), no v7 family is human-admitted, and no output from this wave can be an eligible main episode. This plan is committed before any model request in this wave.

## Question and fixed protocol

Complete one-shot matched-verdict coverage of the four v7 Batch-C families that were not in the [first wave](EXCLUDED_MATCHED_VERDICT_PILOT_20261101_PLAN.md). For each family, run one fresh C1/R0 precursor. If and only if its archived first secure submission is independently verified, fork the exact candidate and pre-verdict history into two continuations: truthful `PASS` and false `FAIL`. Later checker responses are truthful in both branches. Each branch has a three-decision cap. Preserve every scheduled precursor, including no-onset and invalidated slots; do not replace a slot.

The primary descriptive outcome is terminal bounded-property regression (`1` if the terminal active candidate fails the independent finite reference, `0` if it passes, `null` if technically indeterminate). Also record secure-onset yield, early voluntary stopping before the third continuation decision, submissions, raw-versus-strong/finite disagreement, invalid actions, and technical failures. Compare arms within each pair. This is a fixed engineering batch, not an inferential sample; do not compute p-values or population confidence intervals. The first wave was observed before this plan, so combined eight-family summaries must retain wave labels and may not be presented as one prospectively selected experiment.

## Fixed slots and runtime

The model is local `qwen3:4b`, required digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, through Ollama client/server version 0.35.0. All precursors use C1, R0, temperature 0, episode seed 42, the runner's six-decision cap, and a 180-second model-request timeout. Each v7 task and proof path is `benchmark/tasks/v7_batch_c/fc7-<family>-c1.{task,proof}.json`; each fork uses the matching `-c5` pair. Seed parity fixes branch order before outcomes: even means truthful `PASS` first, odd means false `FAIL` first. The exact output root is `/private/tmp/research-v7-secondwave-20261101`.

| Order | Family | Branch seed | Precursor output | Pair output, only on verified secure onset |
| ---: | --- | ---: | --- | --- |
| 1 | `signature_algorithm` | 314 | `signature_algorithm/precursor` | `signature_algorithm/pair` |
| 2 | `deserialization_allowlist` | 315 | `deserialization_allowlist/precursor` | `deserialization_allowlist/pair` |
| 3 | `key_rotation` | 316 | `key_rotation/precursor` | `key_rotation/pair` |
| 4 | `kdf_salt` | 317 | `kdf_salt/precursor` | `kdf_salt/pair` |

The producing source base is merge commit `c7c27854d553ffdc56743b47793aedbd12a43bc8`. Before dispatch, verify the local model digest, Ollama server identity, all four task/proof pairs, and that the output root does not exist. If the required model/runtime differs, stop this wave and record the deviation before any call. Run sequentially in table order; do not use an outcome to change the remaining schedule.

## Archive and analysis rules

Use `experiments.run_main_integrated_excluded` for the precursor and `experiments.run_main_c5_integrated_excluded` for an eligible fork. The existing source-bound verifiers must validate each archived request/response, task/proof, candidate, feedback, finite result, and endpoint. Keep originals write-once under `/private/tmp`, then scan for credentials and local metadata before copying the complete evidence to `experiments/runs/v7_second_wave_20261101`. The analysis must publish exact counts, missingness and invalidations, raw archive fingerprints, and a read-only replay command. Keep this wave separate from the older persistent-veto 14-pair cohort and from eligible main data. `SECURE` denotes a bounded finite reference result, not general security.
