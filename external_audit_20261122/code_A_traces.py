"""Reproducible narrow action/receipt coding for the ten frozen A slots.

Does not read response/thought/history.content fields, execute commands, inspect
published grades, or compare submitted patches. Submission strings are hashed
as exact UTF-8 bytes only. Reviewed classification rules describe observed
actions, not motivation or general capability.
"""
from __future__ import annotations
import datetime
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FROZEN = "7b8e1869d1101c0851935686c20e1003f78922bf75840cab17c702d4aa9e23e2"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def first_line(action):
    return action.splitlines()[0] if action else ""

def file_role(path):
    if "/django/db/" in path or "/django/contrib/" in path or "/astropy/units/" in path:
        return "repository_source"
    if "/tests/" in path:
        return "repository_test"
    if any(part in path for part in ("reproduce", "django_error_project", "sphinx_issue_ugly_enum")):
        return "scratch_or_reproduction"
    if path in ("/django__django/settings.py", "/django__django/models.py"):
        return "scratch_or_reproduction"
    return "unclassified"

def verification_kind(action):
    first = first_line(action)
    if "python -m unittest" in first or first.startswith("./runtests.py "):
        return "test_suite_attempt"
    if re.search(r"\bpython (?:\.\./)?reproduce(?:_bug)?\.py\b", first) or first.startswith("python manage.py shell < ../reproduce.py"):
        return "custom_reproduction_run"
    if first.startswith("sphinx-build "):
        return "custom_build_or_render_check"
    return None

selection_bytes = (ROOT / "selection.json").read_bytes()
assert sha(selection_bytes) == FROZEN
selection = json.loads(selection_bytes)
manifest = json.loads((ROOT / "scratch_A/trace_manifest.json").read_text())
by_id = {row["instance_id"]: row for row in manifest["rows"]}
rows = []
for slot in selection["slots"]:
    if slot["series"] != "A": continue
    instance = slot["instance_id"]
    artifact = by_id[instance]
    row = {
        "series": "A", "submission": selection["submission"]["A"], "instance_id": instance,
        "trace_url": artifact["trace_url"], "trace_sha256": artifact.get("trace_sha256"),
        "raw_trace_path": artifact["raw_path"], "trace_available": artifact["available"],
        "trace_submission_sha256": None,
    }
    if not artifact["available"]:
        row.update(edit_attempt=None, confirmed_edit=None, verification_attempt=None,
                   explicit_finish=None, stop_class="unknown", last_action=None,
                   last_observable_agent_action=None,
                   missing_reason="Verified trace HTTP404; same-submission full-test and Lite traces also HTTP404; no exact full-test path found in pinned catalogue history.",
                   missing_evidence=["scratch_A/trace_manifest.json", "scratch_A/missing_trace_lookup.json",
                                     "scratch_A/alternate_trace_lookup.json", "scratch_A/missing_trace_history_lookup.json"],
                   notes=["Reserved slot retained without replacement; no behavioral or termination claim inferred from trace absence."])
        rows.append(row)
        continue

    raw = Path(artifact["raw_path"]).read_bytes()
    assert sha(raw) == artifact["trace_sha256"]
    data = json.loads(raw)
    trajectory = data["trajectory"]
    assert trajectory and all(isinstance(s["action"], str) and isinstance(s["observation"], str) for s in trajectory)
    history_actions = [(i, h["action"]) for i, h in enumerate(data["history"])
                       if h.get("role") == "assistant" and "action" in h and not h.get("is_demo", False)]
    assert [s["action"] for s in trajectory] == [a for _, a in history_actions]
    exit_status = data["info"].get("exit_status")
    assert exit_status in ("submitted", "submitted (exit_cost)", "exit_cost")
    submission = data["info"].get("submission")
    if isinstance(submission, str):
        row["trace_submission_sha256"] = sha(submission.encode("utf-8"))
        row["trace_submission_utf8_bytes"] = len(submission.encode("utf-8"))
        row["trace_submission_locator"] = "info.submission"
    else:
        row["trace_submission_utf8_bytes"] = None
        row["trace_submission_locator"] = "info.submission absent"

    edit_steps, confirmed, verify, inspections, finish = [], [], [], [], []
    rejected_edits = []
    for index, step in enumerate(trajectory):
        action, observation = step["action"], step["observation"]
        locator = f"trajectory[{index}]"
        if action.startswith("edit ") or action.startswith("create "):
            edit_steps.append({"action_locator": locator + ".action", "command": first_line(action),
                               "action_sha256": sha(action.encode())})
        if action.startswith("edit ") and "File updated." in observation and "NOT been applied" not in observation:
            header = re.search(r"^\[File: (.+?) \(\d+ lines total\)\]", observation)
            assert header is not None
            lines = action.splitlines()
            declaration = re.match(r"edit (\d+):(\d+)$", lines[0])
            replacement_matches = None
            if declaration and lines[-1] == "end_of_edit":
                start = int(declaration[1])
                numbered = {int(number): text for number, text in re.findall(r"(?m)^(\d+):(.*)$", observation)}
                replacement_matches = all(numbered.get(start + j) == line for j, line in enumerate(lines[1:-1]))
            confirmed.append({"action_locator": locator + ".action", "observation_locator": locator + ".observation",
                              "command": first_line(action), "file": header[1], "file_role": file_role(header[1]),
                              "receipt_marker": "File updated.", "replacement_matches_numbered_observation": replacement_matches,
                              "action_sha256": sha(action.encode()), "observation_sha256": sha(observation.encode())})
        elif action.startswith("edit "):
            rejected_edits.append({"action_locator": locator + ".action", "observation_locator": locator + ".observation",
                                   "command": first_line(action), "confirmed_applied": False,
                                   "reason": "No positive File updated receipt; syntax or argument errors are not treated as successful edits."})
        kind = verification_kind(action)
        if kind:
            verify.append({"action_locator": locator + ".action", "observation_locator": locator + ".observation",
                           "kind": kind, "command": first_line(action), "observation_sha256": sha(observation.encode()),
                           "claim_scope": "Command attempted and an observation recorded; no passing-test or repair-success inference."})
        if first_line(action).split(" ")[0] in ("open", "goto", "search_file", "search_dir", "find_file", "find", "ls"):
            inspections.append(index)
        if action.strip() == "submit":
            finish.append({"action_locator": locator + ".action", "history_action_locator": f"history[{history_actions[index][0]}].action",
                           "command": "submit"})

    last = len(trajectory) - 1
    last_action = trajectory[last]["action"]
    last_observation = trajectory[last]["observation"]
    controller = last_action == "exit_cost" and "exit_cost" in exit_status
    acknowledged = bool(finish and exit_status == "submitted" and last_action.strip() == "submit")
    stop_class = "both" if controller and finish else "controller_boundary" if controller else "agent_acknowledged" if acknowledged else "unknown"
    last_agent = last - 1 if controller else last
    scope = sorted(set(receipt["file_role"] for receipt in confirmed))
    notes = [
        "All claims concern the supplied public record; matching trajectory/history action fields validate internal coverage, not external completeness or faithful private reasoning.",
        "Tests and custom reproduction/build commands are counted as attempts regardless of their outcome; source inspection is recorded separately.",
    ]
    if controller:
        notes.append("exit_cost is a recorded controller cost boundary despite occupying an assistant-labelled history action; autosubmission is not an explicit agent submit request.")
    if scope and set(scope) == {"scratch_or_reproduction"}:
        notes.append("Positive edit receipts concern scratch/reproduction files only; they do not establish a repair to existing repository source.")
    if not edit_steps and isinstance(submission, str) and submission.strip():
        notes.append("A nonempty info.submission is present but no edit/create command occurs in either matching action sequence. Attribution of the submitted changes remains unknown; do not infer a model edit from the diff alone.")
    row.update(
        edit_attempt=bool(edit_steps), confirmed_edit=True if confirmed else None,
        verification_attempt=bool(verify), explicit_finish=bool(finish), stop_class=stop_class,
        last_action=first_line(last_action), last_action_locator=f"trajectory[{last}].action",
        last_action_actor="controller_cost_boundary" if controller else "agent_request",
        last_observable_agent_action=first_line(trajectory[last_agent]["action"]),
        last_observable_agent_action_locator=f"trajectory[{last_agent}].action",
        trace_step_count=len(trajectory), history_action_count=len(history_actions),
        history_actions_equal_trajectory=True, info_exit_status=exit_status,
        confirmed_edit_file_roles=scope,
        repository_source_edit_confirmed=any(r["file_role"] == "repository_source" for r in confirmed) if confirmed else None,
        scratch_edit_confirmed=any(r["file_role"] == "scratch_or_reproduction" for r in confirmed) if confirmed else None,
        verification_kinds=sorted(set(v["kind"] for v in verify)),
        static_inspection_observed=bool(inspections),
        evidence={
            "edit_attempts": edit_steps,
            "confirmed_edit_receipts": confirmed,
            "unconfirmed_or_rejected_edits": rejected_edits,
            "verification_attempts": verify,
            "static_inspection_step_indices": inspections,
            "explicit_finish": finish,
            "stop": {"terminal_action_locator": f"trajectory[{last}].action",
                     "terminal_action": last_action, "exit_status_locator": "info.exit_status", "exit_status": exit_status,
                     "terminal_observation_locator": f"trajectory[{last}].observation",
                     "terminal_observation_sha256": sha(last_observation.encode()),
                     "controller_receipt": last_observation if controller else None,
                     "agent_submit_acknowledgment": "info.exit_status == submitted and terminal submit observation recorded" if acknowledged else None},
            "absence_scope": "False means no such command in the full provided internally cross-checked action sequences; it is not a universal claim about unrecorded behavior.",
        }, notes=notes,
    )
    rows.append(row)

result = {
    "series": "A", "submission": selection["submission"]["A"], "selection_sha256": FROZEN,
    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "method": "Assistant primary coding from public action, observation and terminal metadata fields, supported by deterministic extraction; no independent human adjudication assumed.",
    "locators": "Zero-based JSON array indices in the exact SHA256-identified raw .traj files.",
    "read_fields": ["trajectory[].action", "trajectory[].observation", "history[].role", "history[].action", "history[].is_demo", "info.exit_status", "info.submission (UTF-8 hash/length only)"],
    "excluded_fields": ["trajectory[].thought", "trajectory[].response", "history[].content", "published evaluation outcomes"],
    "counting_rules": {
        "edit_attempt": "An observed edit/create command; unsuccessful argument or lint validation still counts as an attempt.",
        "confirmed_edit": "Positive tool File updated receipt with a file header. Null when no model-attributed modification can be confirmed.",
        "verification_attempt": "An executed test-suite, custom reproduction, or build/render command with a recorded observation; static inspection alone is excluded.",
        "explicit_finish": "An exact submit command in matching trajectory and history action fields. Cost-limit exit/autosubmit is excluded.",
        "stop_class": "agent_acknowledged requires submit plus matching terminal submitted status; controller_boundary uses recorded exit_cost; both is reserved for coexisting explicit request and controller boundary.",
    },
    "rows": rows,
    "coverage": {"reserved": len(rows), "available": sum(r["trace_available"] for r in rows),
                 "missing": sum(not r["trace_available"] for r in rows),
                 "stop_classes": dict(Counter(r["stop_class"] for r in rows))},
    "script_sha256": sha(Path(__file__).read_bytes()),
}
with (ROOT / "primary_A.json").open("x", encoding="utf-8") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps(result["coverage"], indent=2))
