# Evidence and sources

The showcase reports the historical audit. Later exploratory pilots are mentioned
as completed follow-up work, without a general causal effect estimate.

| Claim | Evidence |
| --- | --- |
| 40 historical main sessions, five task families | `paper/artifacts/results.json`: `main.n=40`, `main.family_count=5` |
| 20 sessions with the extra hidden rejection rule | Same file: `policy_rejected.n=20` |
| 9 final candidates passed tests but received FAIL | Same file: `policy_rejected.raw_checks_pass=9`, `test_gate_discordance=9` |
| Rule is applied independently after the finite tests | `sandbox/docker_candidate.py`, `condition_reachable` and `passed` assignment |
| Real encryption example | `paper/final.md`, Results, historical slot 10; `docs/MEASUREMENT_FOLLOWUP_20261030.md` |
| Intermediate raw results are missing | `paper/artifacts/results.json`: 81 check observations, zero action raw-check receipts; `paper/final.md`, Measurement validity |
| Improved logging and paired follow-ups exist | `docs/INTEGRATED_ENGINEERING_CHECKPOINT_20261018.md`; `analysis/V7_TEMP_VARIANCE_SECONDWAVE_20261101.md` |

Evidence revision: `9ecd07a3d605cfd812a874835e9b945adc5d5145`.
The SHA-256 of the source result file is recorded in `build_receipt.json`.
This is version linkage, not a third-party validation of the whole study.

Background references:

1. Yao, S., et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models.*
   ICLR. [Primary paper](https://arxiv.org/abs/2210.03629).
2. Shinn, N., et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.*
   [Primary paper](https://arxiv.org/abs/2303.11366).
3. Zakirov project repository: [AiResearch](https://github.com/Imranqsl212/AiResearch).
   The existing manuscript author list has not been altered by this showcase package;
   the showcase team and mentor roles are confirmed separately by the user.

Primary references 1–2 were checked on 3 November 2026. They support the background
on agents using feedback, not the numerical findings of this project.
