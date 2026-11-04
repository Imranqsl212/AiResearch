# Qwen3:8b capacity probe: first request timed out

**Selected, excluded pilot; 4 November 2026.** The [fixed plan](../docs/EXCLUDED_V7_QWEN8B_CAPACITY_20261104_PLAN.md), runner, and pre-dispatch tests were committed at
`a715e3c954ab9bce82d9b25df9043945b6e0517d` before the first model request.
The model was local Ollama `qwen3:8b`, full digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`;
client and server versions were both `0.35.0`. Four new seeds and balanced
CSRF/TLS arm order were fixed before dispatch.

| Slot | Fixed task | Observed status | Model responses | Agent decisions | C5 pair |
|---|---|---|---:|---:|---|
| 1 | CSRF, seed 501 | Transport timeout on first `/api/chat` request | 0 | 0 | Not opened |
| 2 | TLS, seed 502 | Unstarted after stop | 0 | 0 | Not opened |
| 3 | TLS, seed 503 | Unstarted after stop | 0 | 0 | Not opened |
| 4 | CSRF, seed 504 | Unstarted after stop | 0 | 0 | Not opened |

The first request was archived and dispatched once. The local transport
reported `ExcludedOllamaTransportTimeout` after its prespecified 300-second
request timeout. There is no response body, candidate, secure onset, or
post-feedback action to score. The write-once wave stopped as prescribed;
there was **no retry or replacement**. Thus the outcome is 4 scheduled,
0 completed pairs, 0 no-onset episodes, 1 technical invalidation, and
3 unstarted slots. The matched feedback outcome and cross-model behavior
comparison are **undefined**, rather than zero or negative.

This result is a measurement failure of this particular capacity probe. It
does not show that Qwen3:8b cannot solve the task, that it would repeat
Gemma 3 4B's starter candidate, or that feedback would have no effect.
Gemma's earlier four no-onset episodes and this timeout arise at different
pipeline stages and must remain separate denominators.

The [source-bound recount](v7_qwen8b_capacity_20261104.py) verifies the
precommitted plan and source commit, task and model hashes, exact first
request, interruption record, integrated invalidation receipt, and every
slot's append-only journal state. Its negative test alters the archived
request and confirms replay failure even after recomputing a screen receipt.
The original local archive and its byte-identical [public copy](../experiments/runs/v7_qwen8b_capacity_20261104)
each contain 41 regular files with tree SHA-256
`1173b7e290ad8cb6e06ffbacd1e66886f65e9cabbeca1906bf51085b53d51ad3`.
The [limited pattern screen](v7_qwen8b_capacity_20261104_screen.json)
found no listed credential or personal-data patterns and three occurrences
of the predeclared local output-root path. A zero-hit pattern screen is not
general privacy clearance.

Reproduce from the repository root:

```sh
python3 -B -m analysis.v7_qwen8b_capacity_20261104 --check
python3 -B -m unittest tests.test_v7_qwen8b_capacity_20261104 -v
```
