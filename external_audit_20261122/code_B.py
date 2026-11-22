"""Extract narrow observable evidence for the ten frozen B message traces.

No trace commands, model code, tests, or patches are executed. Assistant prose
and replacement source strings are not copied to the repository. Primary
anchors below were inspected independently of published benchmark outcomes.
"""
import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRATCH = Path("/private/tmp/swe_external_B_20261122_1v9q5jxs")
SELECTION_HASH = "7b8e1869d1101c0851935686c20e1003f78922bf75840cab17c702d4aa9e23e2"
ANCHORS = {
    "django__django-15569": {"attempt": 10, "confirmed": 10, "verification": 8},
    "matplotlib__matplotlib-25479": {"attempt": 20, "confirmed": 20, "verification": 6},
    "astropy__astropy-8872": {"attempt": 12, "confirmed": 12, "verification": 6},
    "django__django-16899": {"attempt": 12, "confirmed": 12, "verification": 16},
    "django__django-13406": {"attempt": 68, "confirmed": 68, "verification": 6},
    "sphinx-doc__sphinx-9281": {"attempt": 14, "confirmed": 14, "verification": 6},
    "django__django-13449": {"attempt": 26, "confirmed": 26, "verification": 30},
    "django__django-11880": {"attempt": 20, "confirmed": 20, "verification": 14},
    "sphinx-doc__sphinx-8035": {"attempt": 28, "confirmed": 34, "verification": 24},
    "django__django-11964": {"attempt": 50, "confirmed": 54, "verification": 6},
}


def text(message):
    return "\n".join(part.get("text", "") for part in message.get("content", [])
                     if isinstance(part, dict))


def parsed_call(messages, index):
    message = messages[index]
    assert message["role"] == "assistant" and len(message.get("tool_calls", [])) == 1
    call = message["tool_calls"][0]
    function = call["function"]
    arguments = function["arguments"]
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    return call, function["name"], arguments


def call_evidence(messages, index, purpose):
    call, name, args = parsed_call(messages, index)
    responses = [(i, m) for i, m in enumerate(messages)
                 if m.get("role") == "tool" and m.get("tool_call_id") == call["id"]]
    assert len(responses) == 1
    response_i, response = responses[0]
    response_text = text(response)
    exit_match = re.search(r"\[Command finished with exit code (-?\d+)\]", response_text)
    evidence = {
        "claim": purpose,
        "action_locator": f"$[{index}].tool_calls[0]",
        "call_id": call["id"], "tool": name,
        "command": args.get("command"), "target_path": args.get("path"),
        "response_locator": f"$[{response_i}].content",
        "response_content_sha256": hashlib.sha256(response_text.encode("utf-8")).hexdigest(),
        "response_actor": response["role"],
        "observed_command_exit_code": int(exit_match.group(1)) if exit_match else None,
    }
    if purpose in {"edit_attempt", "confirmed_edit"}:
        assert name == "str_replace_editor" and args["command"] == "str_replace"
        edited = f"The file {args['path']} has been edited." in response_text
        evidence["tool_explicitly_confirms_edit"] = edited
        evidence["paraphrase"] = (
            "The tool explicitly reports that this source file was edited."
            if edited else
            "The requested source replacement has a tool response that does not confirm a modification.")
        if purpose == "confirmed_edit":
            assert edited
    else:
        assert name == "execute_bash"
        evidence["paraphrase"] = (
            "An execute_bash request invokes a custom reproduction/check or documentation build; "
            "the matching response establishes an observed execution attempt, not benchmark success.")
    return evidence


selection_raw = (ROOT / "selection.json").read_bytes()
assert hashlib.sha256(selection_raw).hexdigest() == SELECTION_HASH
selection = json.loads(selection_raw)
manifest = json.loads((SCRATCH / "download_manifest.json").read_text())
downloads = {row["instance_id"]: row for row in manifest["rows"]}
ids = [slot["instance_id"] for slot in selection["slots"] if slot["series"] == "B"]
assert set(ids) == set(ANCHORS) == set(downloads)
rows = []
for instance_id in ids:
    download = downloads[instance_id]
    raw = Path(download["trace_path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == download["trace_sha256"]
    messages = json.loads(raw)
    assert isinstance(messages, list) and all(isinstance(m, dict) for m in messages)
    anchors = ANCHORS[instance_id]
    typed_calls = [(i, call["function"]["name"], call)
                   for i, msg in enumerate(messages)
                   for call in msg.get("tool_calls", [])]
    finish_calls = [(i, name) for i, name, _ in typed_calls
                    if re.search(r"finish|submit|terminate", name, flags=re.I)]
    assert not finish_calls, "New terminal action requires manual recoding"
    assistant_indices = [i for i, msg in enumerate(messages) if msg.get("role") == "assistant"]
    last_i = assistant_indices[-1]
    last_msg = messages[last_i]
    if last_msg.get("tool_calls"):
        last_call, last_name, last_args = parsed_call(messages, last_i)
        last_action = last_name
        last_detail = {"locator": f"$[{last_i}].tool_calls[0]", "tool_call_id": last_call["id"],
                       "tool": last_name, "command": last_args.get("command"),
                       "target_path": last_args.get("path")}
    else:
        last_action = "assistant_message_without_tool_call"
        last_detail = {"locator": f"$[{last_i}]", "role": "assistant",
                       "content_retained": False,
                       "note": "A prose message is observable, but is not by itself a typed finish request."}
    continuation_indices = [i for i, msg in enumerate(messages)
                            if msg.get("role") == "user" and i > 1
                            and "Please continue working" in text(msg)]
    user_controls = [
        {"locator": f"$[{i}].content", "recorded_role": "user",
         "paraphrase": "Requests continued work or an answer followed by finishing; prohibits asking for human help.",
         "origin": "Message role alone does not authenticate whether a human, adapter, or replay inserted it.",
         "subsequent_finish_call_observable": False}
        for i in continuation_indices]
    edits = [call_evidence(messages, anchors["attempt"], "edit_attempt"),
             call_evidence(messages, anchors["confirmed"], "confirmed_edit")]
    verification = call_evidence(messages, anchors["verification"], "verification_attempt")
    # Tool output completion refers to the child command, never to the agent run.
    terminal_msg = messages[-1]
    terminal = {
        "locator": f"$[{len(messages)-1}]",
        "role": terminal_msg["role"],
        "tool_result_name": terminal_msg.get("name"),
        "tool_call_id": terminal_msg.get("tool_call_id"),
        "task_level_terminal_acknowledgment": None,
        "note": "No task-level terminal cause/acknowledgment is retained in this message-list artifact.",
    }
    rows.append({
        "series": "B", "instance_id": instance_id,
        "trace_url": download["trace_url"], "trace_sha256": download["trace_sha256"],
        "trace_bytes": download["bytes"], "local_trace_path": download["trace_path"],
        "trace_available": True, "trace_format": "conversation_message_list",
        "trace_message_count": len(messages),
        "trace_terminal_completeness": "UNVALIDATED",
        "edit_attempt": True, "confirmed_edit": True,
        "verification_attempt": True,
        "verification_kind": ("custom_documentation_build" if instance_id == "sphinx-doc__sphinx-8035"
                              else "custom_behavioral_reproduction_or_check"),
        "formal_test_suite_attempt": None,
        "explicit_finish": None,
        "typed_finish_request_observed_in_available_messages": False,
        "stop_class": "unknown",
        "controller_boundary": None,
        "last_action": last_action, "last_action_evidence": last_detail,
        "continuation_instruction_observed": bool(user_controls),
        "continuation_instruction_evidence": user_controls,
        "trace_submission_sha256": None,
        "trace_submission_note": "No typed final submitted-patch field in the message-list artifact; replacement arguments are not a final submission.",
        "evidence": edits + [verification],
        "terminal_evidence": terminal,
        "coding_limit": (
            "Positive edit and check claims are grounded in typed calls and matching tool replies. "
            "Absent finish/controller events in an unvalidated message snapshot remain unknown. "
            "A shell command exit is not an agent-run termination. No inference about private reasoning, "
            "benchmark resolution, final patch correctness, or general behavior."),
    })

result = {
    "series": "B", "submission": selection["submission"]["B"],
    "selection_sha256": SELECTION_HASH,
    "coded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "coder": "primary automated assistant; independent checker receives raw traces separately",
    "published_outcomes_consulted": False,
    "free_form_reasoning_retained": False,
    "download_manifest": str(SCRATCH / "download_manifest.json"),
    "locator_convention": "Zero-based JSON array indices and tool_call_id matching; content hashes join text blocks with newline.",
    "rows": rows,
}
out = ROOT / "primary_B.json"
with out.open("x", encoding="utf-8") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps({"saved": str(out), "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                  "rows": len(rows), "edit_attempt_true": sum(r["edit_attempt"] is True for r in rows),
                  "confirmed_edit_true": sum(r["confirmed_edit"] is True for r in rows),
                  "verification_attempt_true": sum(r["verification_attempt"] is True for r in rows),
                  "explicit_finish_unknown": sum(r["explicit_finish"] is None for r in rows),
                  "continuation_instructions_observed": sum(r["continuation_instruction_observed"] for r in rows)}))

