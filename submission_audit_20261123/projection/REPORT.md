# A messages-only export erases the final model request

**Controlled, model-free experiment on a historical OpenHands export projection.**

For each of ten previously archived OpenHands message histories, we constructed two explicitly simulated last completions: a `finish` request and a read-only `execute_bash` request with `{"command":"pwd"}`. The command was never executed. We embedded the identical archived message bytes in both logger envelopes, retained the original patch and published grade, and applied the pinned release exporter's exact `jq -r '.messages'` projection. All **10/10 pairs produced byte-identical exports**. Adding the original patch and grade did not distinguish any pair. A proposed completion-bound request receipt distinguished **10/10 pairs**, while leaving actual termination cause unknown in all twenty simulated records.

This is an executable demonstration of a specific export mechanism, not twenty new agent episodes. The information loss was apparent from the source before execution. We do not present the expected collision as an unexpected discovery or claim that either simulated completion occurred historically.

## Rule freeze and evidence

The [protocol](protocol.json) was locally frozen at **2026-11-23 16:20:30.601632 UTC**, before constructing or projecting the simulated pairs. Its SHA-256 is `a14831c9c981f164a597799a3eb54fb03dc7aabfa0b7fa7b1471ab948b9abc93`. The [freeze receipt](protocol_freeze.json) also pins the [provenance manifest](provenance.json). This is a local pre-execution rule freeze, not an external preregistration. The ten histories and their published outcomes had already been examined in the earlier audit; there was no new random or blinded sample selection.

The source is pinned to OpenHands commit `a86275e288087bc7833bc79b0b691ed2ec223205`:

- The [logger](https://github.com/All-Hands-AI/OpenHands/blob/a86275e288087bc7833bc79b0b691ed2ec223205/openhands/llm/llm.py#L234-L263) records input messages and the returned completion in separate fields. The [serializer](https://github.com/All-Hands-AI/OpenHands/blob/a86275e288087bc7833bc79b0b691ed2ec223205/openhands/core/utils/json.py#L13-L26) serializes a model response through its dictionary representation.
- The [exporter](https://github.com/All-Hands-AI/OpenHands/blob/a86275e288087bc7833bc79b0b691ed2ec223205/evaluation/swe_bench/scripts/eval/convert_oh_folder_to_swebench_submission.sh#L11-L18) selects the latest completion file by modification time and projects its message field. This experiment tests that projection **after file selection**; it does not reproduce the file-selection mechanism.
- The [tool definitions and action parser](https://github.com/All-Hands-AI/OpenHands/blob/a86275e288087bc7833bc79b0b691ed2ec223205/openhands/agenthub/codeact_agent/function_calling.py#L297-L349) distinguish `finish` from `execute_bash`. The command schema requires a string `command`; the finish definition declares no parameters. We read these definitions using Python AST processing and checked the simulated JSON requests against them. We did not import the upstream module, instantiate its runtime classes, or execute its action parser.
- The [controller](https://github.com/All-Hands-AI/OpenHands/blob/a86275e288087bc7833bc79b0b691ed2ec223205/openhands/controller/agent_controller.py#L188-L209) separately acknowledges a finish action by changing state; [resource limits](https://github.com/All-Hands-AI/OpenHands/blob/a86275e288087bc7833bc79b0b691ed2ec223205/openhands/controller/agent_controller.py#L430-L443) are another mechanism. Moreover, [CodeAct's user `/exit` route](https://github.com/All-Hands-AI/OpenHands/blob/a86275e288087bc7833bc79b0b691ed2ec223205/openhands/agenthub/codeact_agent/codeact_agent.py#L327-L350) can create a finish action without a new model completion. An event class alone therefore does not identify who requested termination.

All six source-file hashes, the ten raw-message hashes, and official prediction/result source hashes are retained in the manifest. The archived message arrays are real published artifacts; the reconstructed envelopes, completion metadata, and two alternative responses are explicitly synthetic. Their preservation does not establish the exact original provider-request wire bytes or recover any missing historical completion.

## Controlled manipulation

Within each pair, the exact archived message-file byte sequence was embedded unchanged as the `messages` value. Logger metadata, completion identifiers, tool-call identifier, model label, token counters, and provider-style `finish_reason` were identical. The latter was `tool_calls` in both variants: it is not a controller stop cause. Only the requested function and arguments differed.

The original prediction file was reopened and hashed, the actual patch bytes for each issue were extracted, and membership in the original official `resolved` list was rechecked. These original patch bytes and grades were held fixed in both extended observable views. The grade is historical context held constant by design; it is not a newly evaluated result for either simulated continuation.

Only the exact, whitelisted JSON projection was run, as an argument-vector subprocess in a temporary working directory. The downloaded shell script, its prediction converter, upstream Python modules, trajectories, patches, tests, and models were never executed. The run used `jq-1.8.2` and Python `3.14.7`; the historical submission's jq version is unknown.

## Results

| Archived issue | Input messages | Original patch bytes | Original resolved | Projection collision | Request receipt splits pair |
|---|---:|---:|---|---|---|
| `django__django-15569` | 14 | 489 | true | yes | yes |
| `matplotlib__matplotlib-25479` | 32 | 3,713 | false | yes | yes |
| `astropy__astropy-8872` | 20 | 813 | false | yes | yes |
| `django__django-16899` | 48 | 876 | true | yes | yes |
| `django__django-13406` | 200 | 5,933 | true | yes | yes |
| `sphinx-doc__sphinx-9281` | 38 | 7,041 | false | yes | yes |
| `django__django-13449` | 70 | 5,442 | false | yes | yes |
| `django__django-11880` | 32 | 1,512 | true | yes | yes |
| `sphinx-doc__sphinx-8035` | 76 | 2,291 | false | yes | yes |
| `django__django-11964` | 108 | 1,160 | false | yes | yes |

There were no missing inputs or replaced cases. Both projections were also byte-identical to the original published message file in **10/10 pairs**, not merely equal after JSON parsing. This agreement establishes compatibility with the tested export operation; it does not independently prove the provenance of each historical S3 object.

The [results](results.json) contain every simulated response, wrapper digest, projected-output digest, extended-view digest, and proposed receipt. Their SHA-256 is `701f17ff3004276ca0a7dd220482c41f812eb8ed1f5e3f612afe913f8c567ff2`. The [execution receipt](execution_receipt.json) records script hash, versions, and execution time. An offline reconstruction produced the identical result bytes.

For a direct spot check, inspect `results.json` at `/cases/0`, the Django-15569 pair. The two `variants/*/export_sha256` values equal the original input hash, despite different `simulated_response/choices/0/message/tool_calls/0/function/name` values. The receipt's `model_request/finish_requested` differs; its `termination_evidence` fields remain null in both variants.

## What is and is not identifiable

Let `M_i` be an archived message input, `P_i` the original patch, and `G_i` the original published grade. Let the two constructed logger records be `L_i^F = (M_i, R_i^F, ...)` and `L_i^C = (M_i, R_i^C, ...)`, where their final request labels are respectively 1 and 0. The release projection is `E(L) = L.messages`. Therefore the observable views are identical:

`X_i^F = (i, E(L_i^F), P_i, G_i) = (i, E(L_i^C), P_i, G_i) = X_i^C`.

For any deterministic, full-coverage binary classifier whose input is only `X`, the output must be the same for both members of each pair. Exactly one of those two predictions is correct. Across this equally weighted construction, accuracy is therefore **exactly 10/20 = 50%**, with ten errors. A randomized artifact-only classifier likewise has **expected** 50% accuracy. No independence assumption across issues or statistical test is needed: this is a property of the paired construction.

The bound does not apply to an arbitrary real-world distribution, estimate historical finish frequency, or show that half of real runs are misclassified. It excludes access to variant labels, response objects, receipt fields, filenames, or ordering that reveal the constructed label. Our result file intentionally includes those labels as a reproducible witness; this is not a blinded classifier benchmark. Reporting “unknown” is appropriate when evidence is missing, but does not recover the binary request label.

The proposed receipt binds the input, export, original patch/grade, and simulated completion digest to the parsed request's tool name and identifier. The tool name supplies the missing request information; a digest alone only binds bytes. The receipt is a demonstration of sufficient retained information for this narrow distinction, not an authenticated chain of custody or a validated standard.

Crucially, **a final request is not the causal termination event**. Every receipt keeps controller acknowledgment, causal stop actor, termination cause, and terminal event identifier null. A real system would need a separately linked controller acknowledgment or boundary event to support those claims. Adding the request receipt did not resolve historical stopping causes in this experiment.

## Reproduction

From the repository root, with Python and jq installed:

```sh
python3 -B submission_audit_20261123/projection/run_projection.py --check
```

This reads matching cache files or retrieves the pinned public sources into a temporary cache, verifies their hashes, reconstructs the controlled pairs, and compares the result. It does not alter saved experiment files. On the original machine, the entirely offline command is:

```sh
python3 -B submission_audit_20261123/projection/run_projection.py --check --offline
```

The included `--write` mode is the original collection mode and refuses to overwrite `results.json`. Full Git history, model weights, Docker, provider credentials, and the OpenHands Python dependencies are unnecessary. JSON formatting differences in another jq version may cause the strict byte comparison to fail and should be reported rather than silently normalized.

The supported contribution is narrow and concrete: this historical export format is non-injective with respect to the last model request, even when patch and grade are available. The controlled experiment connects that source-level fact to ten real archived input structures and specifies the extra request evidence needed to distinguish the constructed alternatives. It does not demonstrate a new model capability, behavior frequency, or actual termination cause.
