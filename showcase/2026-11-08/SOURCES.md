# Evidence and sources

Prepared on **6 November 2026**. The showcase presents the historical local
audit and a later source-bound analysis of the same saved sessions. Small
exploratory pilots are mentioned as follow-up work, without a general causal
effect estimate. The stop audit is not a new sample of model runs.

| Claim | Evidence |
| --- | --- |
| 40 historical sessions, five task families, one local `qwen3:4b` model | `paper/artifacts/results.json`: `main.n=40`, `main.family_count=5`; `paper/final.md`, Methods |
| 20 sessions used our extra hidden rejection rule | `paper/artifacts/results.json`: `policy_rejected.n=20` |
| Nine final candidates passed the implemented tests but received FAIL | Same file: `policy_rejected.raw_checks_pass=9`, `test_gate_discordance=9`; `paper/final.md`, Table 2 |
| Our rule was applied after the finite tests | `sandbox/docker_candidate.py`: `condition_reachable` and `passed` assignment |
| 14 episodes had an acknowledged terminate call, all immediately after public PASS in repairable tasks | `analysis/HISTORICAL_TERMINATE_LATENCY_20261104.md`, `analysis/historical_terminate_latency_20261104.json`; independently cross-tabulated in `analysis/STOP_LATENCY_CHALLENGE_20261104.md` |
| Median acknowledgement-to-stop interval was 128 seconds in 13 later self-labeled cases | Same latency report: 128.446 seconds, range 27.713–193.514; the fourteenth case was a late timeout and is outside this median |
| No further logged repair attempts followed the first terminate calls | Same report: zero further `attempt` calls, one repeated `terminate` call |
| The historical runner required a separate stopping decision | `analysis/STOP_CONTRACT_CONTROL_20261104.md`, `analysis/stop_contract_control_20261104.json`: model-free frozen-runner control, one extra adapter decision after `STOP_REQUESTED` |
| The prospective collector stops without another adapter decision | `tests/test_v1_collector.py`: `test_terminate_tool_stops_without_another_adapter_decision` |
| Historical intermediate raw check results are missing | `paper/artifacts/results.json`: 81 check observations, zero action raw-check receipts; `paper/final.md`, Measurement validity |
| Improved logging and exploratory paired follow-ups exist | `docs/INTEGRATED_ENGINEERING_CHECKPOINT_20261018.md`; `analysis/V7_TEMP_VARIANCE_SECONDWAVE_20261101.md`; `paper/final.md`, Methods and Results |

Research evidence revision:
**`bf5bc244ce51f5fad92592de8c80cdfad0f88187`**.
Build and validation receipts record artifact provenance and hashes. This
version linkage does not constitute independent review of the whole study.

## Interpretation boundaries

- Nine of twenty is a count within our hidden-rule condition, not a general
  AI error rate. Passing finite tests does not establish complete security.
- All fourteen terminate episodes were post-PASS cases in repairable tasks.
  There were fifteen tool calls because one episode repeated the request.
- The 128-second interval is observed elapsed time, not measured idle time,
  a causal estimate of time wasted, or evidence of refusing to give up.
- The scripted stop control tests the runner protocol; it does not call a
  model or assess code security.
- Missing old step results cannot be recovered by improving later logging.
  Preliminary paired pilots do not establish a general feedback effect.

## Background references

1. Yao, S., et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language
   Models.* ICLR. [Primary paper](https://arxiv.org/abs/2210.03629).
2. Shinn, N., et al. (2023). *Reflexion: Language Agents with Verbal
   Reinforcement Learning.* [Primary paper](https://arxiv.org/abs/2303.11366).
3. Project code, draft and evidence: [AiResearch](https://github.com/Imranqsl212/AiResearch).

Primary references 1–2 were checked on **6 November 2026**. They support the
background on agents using observations and feedback; all numerical showcase
findings come from this project's saved evidence.
