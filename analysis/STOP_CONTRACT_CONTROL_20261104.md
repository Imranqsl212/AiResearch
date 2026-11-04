# A model-free control for the historical stop handshake

**Mechanism check, 4 November 2026.** The historical runner at commit
`98a4dcf414672c1725e4acdb9f08045370aa7f64` was executed in a temporary
source snapshot with a deterministic scripted adapter. This control asked
only whether the runner treats a `terminate` tool acknowledgement as a terminal
decision. It did not call a model, replay its outputs, or evaluate security.

Both controls began with the same synthetic public
`SECURITY_CHECK_PASSED` observation, matching the **success-path** situation
in the historical cases with `terminate`. The sandbox double then produced
the exact public `STOP_REQUESTED` observation shape defined by the frozen
executable sandbox. We used the real frozen `EpisodeRunner`, contracts,
scripted adapter, and trajectory logger; the sandbox and verifier were
purpose-built inert fixtures. Their outputs are protocol controls, not task
results.

The script also reopens the 14 sealed historical terminate histories, checks
their log hashes, and confirms that each was an `RD` or `RW` episode with a
public `SECURITY_CHECK_PASSED` observation before its first `terminate`. No
nominally unavailable `U` episode used this tool.

| Model-free control | Adapter `execute` calls | Logged tool calls | Public observations | Runner stop |
| --- | ---: | --- | --- | --- |
| `attempt` → direct `StopRequest` | 2 | `attempt` | `SECURITY_CHECK_PASSED` | `AGENT_SELF_TERMINATION` |
| `attempt` → `terminate` → `StopRequest` | 3 | `attempt`, `terminate` | `SECURITY_CHECK_PASSED`, `STOP_REQUESTED` | `AGENT_SELF_TERMINATION` |

The second path required an additional adapter `execute` **after** the
`STOP_REQUESTED` observation. Thus the old runner did not use an acknowledged
`terminate` tool call itself as the stopping condition. It waited for a
separate `StopRequest`, a boundary timeout, or a tool budget. This explains
the mechanism behind the [sealed-log latency audit](HISTORICAL_TERMINATE_LATENCY_20261104.md),
which observed 13 later self-labeled episodes with a median 128.446-second
acknowledgement-to-stop interval and one late request ending in `TIMEOUT`.
The control does **not** estimate those episodes' counterfactual completion
time, the model's intent, or whether a two-stage handshake was an intentional
design choice. It also does not provide evidence that an agent failed to give
up on an unavailable task; the historical `terminate` calls occurred in
nominally repairable success paths.

The [JSON result](stop_contract_control_20261104.json) is regenerated from
29 exact historical source files read via the pinned Git commit and 14 sealed
episode logs. The script
checks SHA-256 hashes of the frozen runner and adapter and the executable
sandbox's `terminate` observation branch. Temporary files are deleted after
each run. Reproduce from the repository root:

```sh
python3 -B -m analysis.stop_contract_control_20261104 --check
python3 -B -m unittest -q tests.test_stop_contract_control_20261104
```
