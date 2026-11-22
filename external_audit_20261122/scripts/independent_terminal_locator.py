#!/usr/bin/env python3
"""Locate terminal evidence without executing traces or consulting outcomes.

This schema-specific navigation aid emits JSON pointers, hashes, action names,
and narrow status fields. It does not infer termination cause or completeness.
The independent reviewer supplies those judgments separately. Demo history is
excluded from instance action searches. Model reasoning and patch text are not
included in the output. Only the twenty frozen selection slots are inspected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

SELECTION_SHA256 = "7b8e1869d1101c0851935686c20e1003f78922bf75840cab17c702d4aa9e23e2"
MAX_BYTES = 64 * 1024 * 1024
TERMINAL_COMMAND = re.compile(r"(?:^|[;\n])\s*(?:exit|finish|submit)\s*(?:\d+)?\s*(?:;|$)")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("inspection size limit exceeded")
    return raw, json.loads(raw, object_pairs_hook=unique_pairs)


def text_content(message):
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    return " ".join(part.get("text", "") for part in content if isinstance(part, dict))


def locate_a(data):
    trajectory, history = data["trajectory"], data["history"]
    actual = [(i, entry) for i, entry in enumerate(history)
              if entry.get("role") == "assistant" and not entry.get("is_demo", False)
              and "action" in entry]
    last_index = len(trajectory) - 1
    last = trajectory[-1]
    last_action = last["action"]
    terminal = last_action in {"submit", "exit_cost", "exit_context", "exit_error", "exit_format", "exit_api"}
    observation = last.get("observation", "")
    return {
        "artifact_type": "sweagent_trajectory_with_history_and_info",
        "trajectory_length": len(trajectory),
        "history_length": len(history),
        "instance_action_histories_equal": [entry["action"] for _, entry in actual] == [entry["action"] for entry in trajectory],
        "ignored_demo_terminal_locators": [f"/history/{i}/action" for i, entry in enumerate(history)
                                           if entry.get("is_demo") and entry.get("action") == "submit"],
        "instance_submit_locators": [f"/trajectory/{i}/action" for i, entry in enumerate(trajectory) if entry.get("action") == "submit"],
        "last_record_action": last_action if terminal else "nonterminal action; see locator",
        "last_record_action_locator": f"/trajectory/{last_index}/action",
        "last_history_action_locator": f"/history/{actual[-1][0]}/action",
        "last_response_locator": f"/trajectory/{last_index}/response",
        "last_response_exact_cost_limit_message": last.get("response") == "Exit due to cost limit",
        "last_response_has_exact_submit_line": "submit" in last.get("response", "").splitlines(),
        "last_observation_locator": f"/trajectory/{last_index}/observation",
        "last_observation_status": observation if observation in {"Exited", "Exited (autosubmitted)"} else "body omitted",
        "exit_status": data.get("info", {}).get("exit_status"),
        "exit_status_locator": "/info/exit_status",
        "previous_action_locator": f"/trajectory/{last_index - 1}/action" if last_index else None,
        "previous_action_type": trajectory[-2]["action"].split(maxsplit=1)[0] if last_index else None,
    }


def locate_b(data):
    calls = []
    candidates = []
    assistants = []
    for i, message in enumerate(data):
        if message.get("role") != "assistant":
            continue
        assistants.append(i)
        for j, call in enumerate(message.get("tool_calls", [])):
            function = call.get("function", {})
            location = f"/{i}/tool_calls/{j}/function"
            record = {"location": location, "name": function.get("name"), "id": call.get("id")}
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments, object_pairs_hook=unique_pairs)
            if isinstance(arguments, dict):
                for key in ("command", "code"):
                    value = arguments.get(key)
                    if isinstance(value, str):
                        record[f"{key}_sha256"] = sha256(value.encode())
                        if TERMINAL_COMMAND.search(value):
                            candidates.append({"location": location + "/arguments", "kind": "terminal-command candidate"})
            if function.get("name") in {"finish", "submit", "exit"}:
                candidates.append({"location": location + "/name", "kind": "terminal-function candidate"})
            calls.append(record)
    last = data[-1]
    text = text_content(last)
    last_call = calls[-1] if calls else None
    return {
        "artifact_type": "chat_message_list_without_controller_state",
        "message_count": len(data),
        "last_role": last.get("role"),
        "last_message_locator": f"/{len(data) - 1}",
        "last_assistant_locator": f"/{assistants[-1]}",
        "last_assistant_has_tool_calls": bool(data[assistants[-1]].get("tool_calls")),
        "tool_names_observed": sorted({call["name"] for call in calls}),
        "terminal_candidates": candidates,
        "last_tool_call": last_call,
        "last_tool_response_matches": bool(last_call and last.get("role") == "tool" and last.get("tool_call_id") == last_call["id"]),
        "last_tool_response_command_exit_zero": last.get("role") == "tool" and "Command finished with exit code 0" in text,
        "last_message_is_continuation_prompt": last.get("role") == "user" and text.startswith("Please continue working on the task"),
        "run_termination_metadata_present": False,
        "metadata_scope_note": "The inspected top-level representation is a chat-message list, not an event stream or terminal controller record.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--a-root", required=True, type=Path)
    parser.add_argument("--b-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw_selection, selection = read_json(args.selection)
    if sha256(raw_selection) != SELECTION_SHA256:
        raise ValueError("selection hash differs from the independent review freeze")
    rows = []
    for slot in selection["slots"]:
        series, instance_id = slot["series"], slot["instance_id"]
        root, suffix = (args.a_root, ".traj") if series == "A" else (args.b_root, ".json")
        path = root / (instance_id + suffix)
        url = "https://swe-bench-submissions.s3.amazonaws.com/verified/" + selection["submission"][series] + "/trajs/" + path.name
        row = {"series": series, "instance_id": instance_id, "raw_path": str(path), "trace_url": url}
        try:
            raw, data = read_json(path)
            row.update(available=True, raw_sha256=sha256(raw), bytes=len(raw))
            row["evidence"] = locate_a(data) if series == "A" else locate_b(data)
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            row.update(available=False, inspection_error=str(exc))
        rows.append(row)
    result = {"method": "independent_structural_locator_v2", "selection_sha256": SELECTION_SHA256,
              "warning": "Navigation evidence only; no automatic causal classification or completeness assertion.", "rows": rows}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
