# Excluded v1 JSON action protocol pilot — 3 October 2026

This is an engineering receipt for one local model response. It is **not** a main-study episode or evidence of repair, stopping judgment, or a RAG effect.

## Frozen invocation and result

From the repository root:

```sh
python3 -B -m experiments.run_v1_live_pilot \
  --condition C4 --retrieval-mode R0 --model qwen3:4b \
  --max-steps 1 --max-output-tokens 256 \
  --output-dir experiments/v1_live_json_pilot_20261003
```

The output directory and episode ID are create-once. The local episode manifest is [`experiments/v1_live_json_pilot_20261003/live-c4-r0.manifest.json`](../experiments/v1_live_json_pilot_20261003/live-c4-r0.manifest.json); the directory is now tracked in this local Git branch. A clone of a remote branch containing these commits would include the pilot trace; check the remote state separately. The exact initial provider request envelope, including the starter failure, is saved as the hash-linked prompt artifact. The tested protocol sends Ollama `/api/chat` a two-field JSON action schema via `format`, with `think: false`, temperature `0`, seed `7`, context window `8192`, and output cap `256`. These fields follow Ollama's [chat API](https://docs.ollama.com/api/chat), [structured output](https://docs.ollama.com/capabilities/structured-outputs), and [thinking control](https://docs.ollama.com/capabilities/thinking) documentation.

The installed model was `qwen3:4b`, Q4_K_M, full local digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`. The episode recorded exactly **one provider request**: after the standardized starter failed and the public C4 contradiction witness was delivered, the model produced a valid structured `INSPECT` action. The action did not run the checker. The collector stopped at the deliberately set one-action budget, so `STOP=BUDGET`, `remaining_action_budget=0`, and `final_claim_status=unknown`. The provider reported 722 input and 15 output tokens. No agent `attempt`, explicit `claim`, or C4 stop decision was observed.

The v1 loader verified the saved oracle proof and Git commit; the manifest says `phase=pilot`, `eligible_for_main_analysis=false`, and `invalidated=false`. The live response needed no protocol discard (`discarded_unstructured_model_messages=0`). The adapter retains only a locally validated action or claim, drops any provider `thinking` field, and marks malformed/no-action responses as protocol errors. A mocked integration test injects a distinct thinking marker and verifies it is absent from the prompt, log, schedule, and manifest. This validates storage behavior, not whether the provider internally generated reasoning.

## Artifact and source digests

| Item | SHA-256 or ID |
| --- | --- |
| Saved prompt artifact | `7dccbe61bf9ef7fd7f13003984c893f624dff9c3feccbd655b504c896b20b3d9` |
| Saved JSONL log | `6eaf7ec6b1554a35ec449e543cefd395a6043a5db84ca684844afd4a762736d0` |
| Saved manifest file | `4588f2aa2fb6ccf52b5c20366dc880156916d988d89aa2665753d567bec89b8f` |
| `agent/v1_ollama_adapter.py` at live run | `bc7af6306c32585d3ccb9d9ccf2f3925a9da1c8fa5cacba1845906d577ecdff5` |
| `agent/prompts/v1_system.txt` at live run | `18f7090334048ac2641a13eb58977eadc1b64cfd1f88f8461d3f880656aa0b2c` |
| `experiments/v1_collector.py` at live run | `0a2e16ee30e6894c3c501dc3a3356150139d9bf169dec68b6715e4d1a45987c1` |
| `experiments/run_v1_live_pilot.py` at live run | `36381c4f0e2aaf5b0832f68b419b69f5178436e19f2bc6b2f724ae50f557d029` |
| Git HEAD recorded by collector | `af0eb3f9df5a2d1a17e456954c2cca93e247a703` |

The source files above were uncommitted at collection time; Git HEAD alone is insufficient to reconstruct this protocol. The file digests and locally retained artifacts distinguish this pilot from earlier tool-call pilots. This one-action run did not demonstrate a structured `attempt` or explicit `claim`; the later [C1 trajectory checks](V1_LIVE_C1_TRAJECTORY_PILOT.md) recorded submissions and termination. Main collection remains blocked.

## Verification

`PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_v1_ollama_adapter tests.test_v1_collector tests.test_v1_analysis tests.test_retrieval_v1 -q` passed 46 tests after the run. The tested parser rejects prose, duplicate JSON keys, extra fields, malformed policies, and mixed tool-call/JSON responses. It never treats such a no-action response as voluntary stopping.
