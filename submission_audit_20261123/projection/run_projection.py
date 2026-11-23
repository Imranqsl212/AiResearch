"""Controlled synthetic-completion projection experiment; never run trace code.

Only the pinned exporter's whitelisted `jq -r .messages` projection is executed.
Upstream Python/shell sources are read as text or AST, never imported or run.
Raw public files live in temporary caches. --write creates new result files;
--check reconstructs the experiment and compares the saved result without edits.
"""
from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
PROTOCOL_SHA256 = "a14831c9c981f164a597799a3eb54fb03dc7aabfa0b7fa7b1471ab948b9abc93"
MAX_BYTES = 64 * 1024 * 1024


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def unique_pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique_pairs)


def read(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    need(len(raw) <= MAX_BYTES, f"Inspection size limit exceeded: {path}")
    return raw


def obtain(meta, offline, cache):
    cache_file = cache / meta["sha256"]
    for path in (Path(meta["cache_hint"]), cache_file):
        try:
            raw = read(path)
        except OSError:
            continue
        if sha(raw) == meta["sha256"] and len(raw) == meta["bytes"]:
            return raw
    need(not offline, f"No matching cache for {meta['url']}")
    need(meta["url"].startswith("https://"), "Only public HTTPS retrieval is allowed")
    with urllib.request.urlopen(meta["url"], timeout=45) as response:
        raw = response.read(MAX_BYTES + 1)
    need(len(raw) <= MAX_BYTES and sha(raw) == meta["sha256"] and len(raw) == meta["bytes"],
         f"Public artifact receipt mismatch: {meta['url']}")
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
        stream.write(raw)
        temporary = Path(stream.name)
    temporary.replace(cache_file)
    return raw


def tool_definition(tree, variable):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == variable for t in node.targets):
            function = next(k.value for k in node.value.keywords if k.arg == "function")
            keywords = {k.arg: k.value for k in function.keywords}
            return {"name": ast.literal_eval(keywords["name"]),
                    "parameters": ast.literal_eval(keywords["parameters"]) if "parameters" in keywords else None}
    raise ValueError(f"Missing upstream tool definition: {variable}")


def validate_sources(sources):
    exporter = sources["evaluation/swe_bench/scripts/eval/convert_oh_folder_to_swebench_submission.sh"].decode()
    projection_line = 'cat "$latest_json" | jq -r \'.messages\' > "$NEW_FOLDER_PATH/trajs/$instance_id.json"'
    need(sum(line.strip() == projection_line for line in exporter.splitlines()) == 1,
         "Pinned exporter projection differs")
    # The expression is taken from this exact, validated line, then whitelisted.
    expression = projection_line.split("jq -r '", 1)[1].split("'", 1)[0]
    need(expression == ".messages", "Projection expression outside whitelist")
    logger = sources["openhands/llm/llm.py"].decode()
    need("'messages': messages" in logger and "'response': resp" in logger,
         "Logger does not preserve separate input and completion fields")
    serializer = sources["openhands/core/utils/json.py"].decode()
    need("isinstance(obj, ModelResponse)" in serializer and "return obj.model_dump()" in serializer,
         "Upstream completion serialization differs")
    function_source = sources["openhands/agenthub/codeact_agent/function_calling.py"].decode()
    tree = ast.parse(function_source)
    finish, continuing = tool_definition(tree, "FinishTool"), tool_definition(tree, "CmdRunTool")
    need(finish == {"name": "finish", "parameters": None}, "Finish tool definition differs")
    need(continuing["name"] == "execute_bash" and continuing["parameters"]["type"] == "object"
         and continuing["parameters"]["required"] == ["command"]
         and continuing["parameters"]["properties"]["command"]["type"] == "string",
         "Continuing tool schema differs")
    need("action = CmdRunAction(**arguments)" in function_source
         and "action = AgentFinishAction()" in function_source
         and "json.loads(tool_call.function.arguments)" in function_source,
         "Upstream action parser branches differ")
    controller = sources["openhands/controller/agent_controller.py"].decode()
    need("elif isinstance(action, AgentFinishAction):" in controller
         and "await self.set_agent_state_to(AgentState.FINISHED)" in controller
         and "if self.state.iteration >= self.state.max_iterations:" in controller,
         "Controller acknowledgment or resource-boundary context differs")
    agent = sources["openhands/agenthub/codeact_agent/codeact_agent.py"].decode()
    need("latest_user_message.strip() == '/exit'" in agent,
         "Expected separate user-triggered finish route missing")
    return expression, {"finish": finish, "continue": continuing}


def response_for(instance, tool_name, arguments):
    return {"id": "simulated-" + instance, "object": "chat.completion", "created": 0,
            "model": "synthetic-projection-control", "choices": [{"index": 0, "finish_reason": "tool_calls",
            "message": {"role": "assistant", "content": "", "tool_calls": [{"id": "simulated_call_0",
            "type": "function", "function": {"name": tool_name, "arguments": canonical(arguments).decode()}}]}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}


def validate_request(response, definition):
    need(len(response["choices"]) == 1, "Expected a single completion choice")
    message = response["choices"][0]["message"]
    need(message["role"] == "assistant" and len(message["tool_calls"]) == 1, "Invalid simulated request structure")
    call = message["tool_calls"][0]
    need(call["type"] == "function" and call["function"]["name"] == definition["name"], "Tool name mismatch")
    arguments = decode(call["function"]["arguments"])
    if definition["parameters"] is None:
        need(arguments == {}, "The finish control must have empty arguments")
    else:
        need(set(arguments) == {"command"} and isinstance(arguments["command"], str)
             and arguments["command"] == "pwd", "Continue control must request read-only pwd")
    return call


def frame(*parts):
    return b"projection-view-v1" + b"".join(len(part).to_bytes(8, "big") + part for part in parts)


def experiment(provenance, protocol, offline, cache):
    sources = {meta["repository_path"]: obtain(meta, offline, cache) for meta in provenance["source_files"]}
    expression, definitions = validate_sources(sources)
    jq = shutil.which("jq")
    need(jq is not None, "jq is required; only its whitelisted JSON projection will run")
    jq_version = subprocess.check_output([jq, "--version"], text=True).strip()
    results_raw = obtain(provenance["official_endpoint_sources"]["results"], offline, cache)
    resolved = set(decode(results_raw)["resolved"])
    predictions_raw = obtain(provenance["official_endpoint_sources"]["predictions"], offline, cache)
    reserved = {row["instance_id"] for row in provenance["inputs"]}
    need(len(reserved) == len(provenance["inputs"]) == 10, "Expected all ten frozen B inputs")
    predictions = {}
    for line_number, line in enumerate(predictions_raw.splitlines(), 1):
        row = decode(line)
        if row["instance_id"] in reserved:
            need(row["instance_id"] not in predictions, "Ambiguous prediction rows")
            predictions[row["instance_id"]] = (line_number, row["model_patch"].encode())
    need(set(predictions) == reserved, "Missing original patch")
    cases = []
    with tempfile.TemporaryDirectory(prefix="projection_isolation_") as isolated:
        for source in provenance["inputs"]:
            instance = source["instance_id"]
            meta = {"url": source["messages_url"], "sha256": source["messages_sha256"],
                    "bytes": source["messages_bytes"], "cache_hint": source["messages_cache_hint"]}
            messages_raw = obtain(meta, offline, cache)
            messages = decode(messages_raw)
            need(isinstance(messages, list) and len(messages) == source["message_count"]
                 and all(isinstance(m, dict) and m.get("role") in {"system", "user", "assistant", "tool"} for m in messages),
                 f"Unexpected genuine input structure: {instance}")
            line_number, patch = predictions[instance]
            grade = instance in resolved
            need(line_number == source["prediction_line_1_based"] and sha(patch) == source["patch_sha256"]
                 and len(patch) == source["patch_bytes"] and grade == source["published_resolved"],
                 f"Original endpoint evidence differs: {instance}")
            variants = {}
            outputs = {}
            for variant in ("finish", "continue"):
                manipulation = protocol["manipulation"][variant]
                response = response_for(instance, manipulation["tool_name"], manipulation["arguments"])
                call = validate_request(response, definitions[variant])
                prefix = b'{"messages":'
                suffix = b',"response":' + canonical(response) + b',"args":[],"kwargs":{},"timestamp":0,"cost":0}'
                envelope = prefix + messages_raw + suffix
                need(envelope[len(prefix):len(prefix) + len(messages_raw)] == messages_raw,
                     "Input message bytes changed")
                need(decode(envelope)["messages"] == messages, "Envelope input structure changed")
                projected = subprocess.run([jq, "-r", expression], input=envelope, capture_output=True,
                                           cwd=isolated, timeout=20, check=True).stdout
                need(decode(projected) == messages, "Projection did not preserve the input message value")
                view = frame(instance.encode(), projected, patch, canonical(grade))
                receipt = {
                    "schema": "proposed-final-request-receipt-v1", "provenance": "explicitly_simulated_completion",
                    "instance_id": instance, "input_messages_sha256": sha(messages_raw),
                    "projected_messages_sha256": sha(projected), "original_patch_sha256": sha(patch),
                    "original_published_resolved": grade, "completion_sha256": sha(canonical(response)),
                    "model_request": {"tool_call_id": call["id"], "tool_name": call["function"]["name"],
                                      "finish_requested": call["function"]["name"] == "finish"},
                    "termination_evidence": {"controller_acknowledged": None, "causal_stop_actor": None,
                                             "termination_cause": None, "terminal_event_id": None},
                }
                variants[variant] = {"simulated_response": response, "logger_envelope_sha256": sha(envelope),
                                     "export_sha256": sha(projected), "extended_observable_view_sha256": sha(view),
                                     "receipt": receipt, "receipt_sha256": sha(canonical(receipt))}
                outputs[variant] = projected
            collision = outputs["finish"] == outputs["continue"]
            extended_collision = variants["finish"]["extended_observable_view_sha256"] == variants["continue"]["extended_observable_view_sha256"]
            receipt_split = variants["finish"]["receipt_sha256"] != variants["continue"]["receipt_sha256"]
            need(collision and extended_collision and receipt_split, f"Predicted mechanism failed: {instance}")
            cases.append({"instance_id": instance, "input_messages_sha256": sha(messages_raw),
                          "input_messages_bytes": len(messages_raw), "message_count": len(messages),
                          "original_patch_sha256": sha(patch), "original_patch_bytes": len(patch),
                          "original_published_resolved": grade, "exact_input_bytes_held_fixed": True,
                          "projection_collision": collision, "extended_view_collision": extended_collision,
                          "receipt_split": receipt_split,
                          "projected_bytes_equal_archived_export": outputs["finish"] == messages_raw,
                          "actual_termination_cause": None, "variants": variants})
    result = {"schema_version": "projection-result-v1", "protocol_sha256": PROTOCOL_SHA256,
              "provenance_sha256": sha(read(ROOT / "provenance.json")),
              "upstream_code_commit": provenance["upstream_code_commit"], "projection_expression": expression,
              "counts": {"archived_inputs": 10, "simulated_completions": 20, "executed_agent_runs": 0,
                         "projection_collisions": sum(c["projection_collision"] for c in cases),
                         "extended_view_collisions": sum(c["extended_view_collision"] for c in cases),
                         "receipt_splits": sum(c["receipt_split"] for c in cases), "missing_inputs": 0,
                         "synthetic_records_with_observed_termination_cause": 0},
              "balanced_construction_bound": {"artifact_only_full_coverage_accuracy": 0.5,
                                               "deterministic_errors_per_20": 10,
                                               "scope": "mathematical bound for these equally weighted simulated opposite-label pairs only"},
              "cases": cases}
    return result, jq_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=Path(tempfile.gettempdir()) / "submission_projection_20261123")
    args = parser.parse_args()
    protocol_raw, provenance_raw = read(ROOT / "protocol.json"), read(ROOT / "provenance.json")
    freeze = decode(read(ROOT / "protocol_freeze.json"))
    need(sha(protocol_raw) == PROTOCOL_SHA256 == freeze["protocol_sha256"], "Frozen protocol changed")
    protocol, provenance = decode(protocol_raw), decode(provenance_raw)
    need(sha(provenance_raw) == protocol["provenance_sha256"] == freeze["provenance_sha256"], "Frozen provenance changed")
    need(not args.write or not (ROOT / "results.json").exists(), "Result already exists; use --check")
    result, jq_version = experiment(provenance, protocol, args.offline, args.cache_dir)
    payload = (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode()
    if args.write:
        with (ROOT / "results.json").open("xb") as stream:
            stream.write(payload)
        execution = {"executed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     "protocol_sha256": PROTOCOL_SHA256, "script_sha256": sha(read(Path(__file__))),
                     "result_sha256": sha(payload), "jq_version": jq_version, "python_version": sys.version.split()[0],
                     "offline": args.offline, "upstream_programs_executed": [],
                     "executed_projection": ["jq", "-r", ".messages"], "agent_or_trajectory_commands_executed": []}
        with (ROOT / "execution_receipt.json").open("x") as stream:
            json.dump(execution, stream, indent=2)
            stream.write("\n")
    else:
        need(read(ROOT / "results.json") == payload, "Saved result differs from reconstructed controlled experiment")
    print("PASS: 10 archived inputs; 20 explicitly simulated completions; 0 agent runs.")
    print("PASS: 10/10 release-projection collisions; 10/10 collisions with original patch and grade retained.")
    print("PASS: 10/10 request-receipt splits; actual termination cause remains unknown in all 20 simulated records.")
    print(f"Projection: {jq_version}, jq -r .messages. Result SHA-256: {sha(payload)}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
