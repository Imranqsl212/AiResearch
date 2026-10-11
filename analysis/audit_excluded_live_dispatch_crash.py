"""Read-only audit of write-once, excluded live-dispatch slot directories.

This is an evidence inventory, not a recovery path. In particular a saved
dispatch-start without a dispatch-return cannot establish whether a send
occurred. The audit never calls a transport or writes to the slot directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from experiments.main_collector import DECISION_CAP, SAFE_ID, _canonical, _response_action
from experiments.main_live_dispatch_excluded import (
    VERSION as DISPATCH_VERSION,
    _check_response_envelope,
    verify_excluded_live_trace,
)


AUDIT_VERSION = "excluded-live-crash-audit-0.1.0"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
NUMBERED = re.compile(
    r"(request|response|dispatch-start|dispatch-return|decision|interruption)"
    r"-([0-9]{6})\.(bin|json)\Z"
)
KIND_EXT = {
    "request": "bin", "response": "bin", "dispatch-start": "json",
    "dispatch-return": "json", "decision": "json", "interruption": "json",
}
ROOT_FILES = {
    "plan_snapshot.json", "source_inventory.json", "slot_open.json",
    "slot_receipt.json",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_source_name(name: Any) -> bool:
    if not isinstance(name, str) or not name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and all(piece not in {"", ".", ".."}
                                          for piece in name.split("/"))


def _strict_object(raw: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject(value: str) -> None:
        raise ValueError(f"non-JSON constant {value}")

    value = json.loads(raw, object_pairs_hook=unique, parse_constant=reject)
    if not isinstance(value, dict):
        raise ValueError("JSON value is not an object")
    return value


def audit_excluded_live_slot(slot_dir: Path) -> dict[str, Any]:
    """Classify an existing slot from local bytes, without repairing or retrying.

    ``integrity=failed`` means the observed bytes are malformed or contradict
    the writer's ordering/hash contract. It does not attribute a cause:
    interruption, storage failure, and tampering can look alike. A clean
    prefix without a final receipt is ``integrity=incomplete``.
    """
    root = Path(slot_dir).absolute()
    issues: list[dict[str, str]] = []
    files: dict[str, Path] = {}
    dirs: set[str] = set()
    parsed: dict[str, dict[str, Any] | None] = {}

    def issue(code: str, path: str = "") -> None:
        item = {"code": code}
        if path:
            item["path"] = path
        if item not in issues:
            issues.append(item)

    def read(rel: str) -> bytes | None:
        path = files.get(rel)
        if path is None:
            return None
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    issue("NONREGULAR_PATH", rel)
                    return None
                return handle.read()
        except OSError:
            issue("UNREADABLE_PATH", rel)
            return None

    def json_record(rel: str, *, newline: bool = True) -> dict[str, Any] | None:
        if rel in parsed:
            return parsed[rel]
        raw = read(rel)
        if raw is None:
            parsed[rel] = None
            return None
        try:
            value = _strict_object(raw)
            expected = _canonical(value) + (b"\n" if newline else b"")
            if raw != expected:
                issue("NONCANONICAL_JSON", rel)
        except (UnicodeError, ValueError, TypeError, RecursionError):
            issue("INVALID_JSON", rel)
            value = None
        parsed[rel] = value
        return value

    if root.is_symlink() or not root.is_dir():
        issue("SLOT_DIRECTORY_MISSING_OR_UNSAFE")
    else:
        def walk_error(_: OSError) -> None:
            issue("DIRECTORY_UNREADABLE")

        for parent, child_dirs, child_files in os.walk(root, followlinks=False,
                                                        onerror=walk_error):
            parent_path = Path(parent)
            for name in list(child_dirs):
                path = parent_path / name
                rel = path.relative_to(root).as_posix()
                if path.is_symlink():
                    issue("SYMLINK_PATH", rel)
                    child_dirs.remove(name)
                else:
                    dirs.add(rel)
            for name in child_files:
                path = parent_path / name
                rel = path.relative_to(root).as_posix()
                try:
                    mode = path.lstat().st_mode
                except OSError:
                    issue("UNREADABLE_PATH", rel)
                    continue
                if not stat.S_ISREG(mode):
                    issue("SYMLINK_PATH" if stat.S_ISLNK(mode) else "NONREGULAR_PATH", rel)
                else:
                    files[rel] = path

    for rel in ("plan_snapshot.json", "source_inventory.json", "slot_open.json"):
        if rel not in files:
            issue("INITIALIZATION_ARTIFACT_MISSING", rel)
    opened = json_record("slot_open.json")
    plan = json_record("plan_snapshot.json", newline=False)
    inventory = json_record("source_inventory.json")
    slot_id: str | None = None
    source_hashes: dict[str, str] = {}
    if opened is not None:
        slot_id = opened.get("slot_id") if isinstance(opened.get("slot_id"), str) else None
        if (opened.get("schema_version") != DISPATCH_VERSION
                or opened.get("phase") != "pilot"
                or opened.get("status") != "EXCLUDED_LIVE_DISPATCH_OPEN"
                or opened.get("eligible_for_main_analysis") is not False
                or opened.get("main_dispatch_allowed") is not False
                or type(opened.get("replacement_count")) is not int
                or opened.get("replacement_count") != 0
                or slot_id is None or SAFE_ID.fullmatch(slot_id) is None
                or not isinstance(opened.get("observed_model"), dict)
                or not isinstance(opened.get("observed_inference_config"), dict)
                or type(opened.get("episode_seed")) is not int):
            issue("OPEN_RECORD_CONTRADICTION", "slot_open.json")
    if inventory is not None:
        candidate = inventory.get("source_file_sha256s")
        if (inventory.get("schema_version") != DISPATCH_VERSION
                or not isinstance(candidate, dict) or not candidate
                or any(not _safe_source_name(name) or not isinstance(digest, str)
                       or HEX64.fullmatch(digest) is None
                       for name, digest in candidate.items())):
            issue("SOURCE_INVENTORY_CONTRADICTION", "source_inventory.json")
        else:
            source_hashes = candidate
    if plan is not None:
        plan_models = plan.get("models")
        plan_model = (plan_models[0] if isinstance(plan_models, list)
                      and len(plan_models) == 1 and isinstance(plan_models[0], dict)
                      else {})
        plan_sources = plan.get("source_file_sha256s")
        sources_valid = (isinstance(plan_sources, dict) and bool(plan_sources)
                         and all(_safe_source_name(name) and isinstance(digest, str)
                                 and HEX64.fullmatch(digest) is not None
                                 for name, digest in plan_sources.items()))
        if (plan.get("phase") != "main"
                or plan.get("status") != "PROPOSED_MAIN_UNGATED"
                or plan.get("eligible_for_main_analysis") is not False
                or plan.get("main_execution_implemented") is not False
                or not plan_model
                or not isinstance(plan_model.get("name"), str)
                or not plan_model["name"]
                or not isinstance(plan_model.get("digest"), str)
                or HEX64.fullmatch(plan_model["digest"]) is None
                or not isinstance(plan.get("inference_config"), dict)
                or plan["inference_config"].get("max_steps") != DECISION_CAP
                or not isinstance(plan.get("slots"), list)
                or not sources_valid):
            issue("PLAN_CONTRADICTION", "plan_snapshot.json")
        if opened is not None:
            models = plan.get("models")
            planned_model = models[0] if isinstance(models, list) and len(models) == 1 else None
            observed_model = opened.get("observed_model")
            observed_model = observed_model if isinstance(observed_model, dict) else {}
            if (opened.get("plan_sha256") != _sha(read("plan_snapshot.json") or b"")
                    or observed_model != planned_model
                    or opened.get("observed_inference_config") != plan.get("inference_config")):
                issue("PLAN_OPEN_MISMATCH", "plan_snapshot.json")
            slots = plan.get("slots")
            matches = ([row for row in slots if isinstance(row, dict)
                        and row.get("slot_id") == slot_id]
                       if isinstance(slots, list) else [])
            if (len(matches) != 1 or type(matches[0].get("episode_seed")) is not int
                    or matches[0].get("episode_seed") != opened.get("episode_seed")
                    or matches[0].get("model") != observed_model.get("name")
                    or matches[0].get("model_digest") != observed_model.get("digest")
                    or any(not _safe_source_name(matches[0].get(f"{kind}_path"))
                           or not isinstance(plan_sources, dict)
                           or plan_sources.get(matches[0].get(f"{kind}_path")) !=
                           matches[0].get(f"{kind}_sha256")
                           for kind in ("task", "proof"))):
                issue("SLOT_PLAN_MISMATCH", "plan_snapshot.json")
        if source_hashes and plan.get("source_file_sha256s") != source_hashes:
            issue("PLAN_SOURCE_INVENTORY_MISMATCH", "source_inventory.json")
        if inventory is None and not source_hashes:
            candidate = plan.get("source_file_sha256s")
            if (isinstance(candidate, dict) and candidate
                    and all(_safe_source_name(name) and isinstance(digest, str)
                            and HEX64.fullmatch(digest) is not None
                            for name, digest in candidate.items())):
                source_hashes = candidate

    expected_files = set(ROOT_FILES)
    expected_dirs = {"source_archive"}
    for name, digest in source_hashes.items():
        rel = "source_archive/" + name
        expected_files.add(rel)
        parts = Path(rel).parts
        expected_dirs.update(Path(*parts[:i]).as_posix() for i in range(1, len(parts)))
        raw = read(rel)
        if raw is None:
            issue("ARCHIVED_SOURCE_MISSING", rel)
        elif _sha(raw) != digest:
            issue("ARCHIVED_SOURCE_HASH_MISMATCH", rel)

    numbered: dict[int, set[str]] = {}
    for rel in files:
        if "/" in rel:
            if rel not in expected_files and not (
                not source_hashes and rel.startswith("source_archive/")
                and _safe_source_name(rel[len("source_archive/"):])
            ):
                issue("UNEXPECTED_PATH", rel)
            continue
        match = NUMBERED.fullmatch(rel)
        if match:
            kind, digits, extension = match.groups()
            sequence = int(digits)
            if extension != KIND_EXT[kind] or not 1 <= sequence <= DECISION_CAP:
                issue("UNEXPECTED_PATH", rel)
            else:
                numbered.setdefault(sequence, set()).add(kind)
            continue
        if rel not in expected_files:
            issue("UNEXPECTED_PATH", rel)
    for rel in dirs - expected_dirs:
        if source_hashes or not rel.startswith("source_archive/"):
            issue("UNEXPECTED_PATH", rel)
    if source_hashes and "source_archive" not in dirs:
        issue("ARCHIVED_SOURCE_DIRECTORY_MISSING", "source_archive")

    config_sha: str | None = None
    if opened is not None:
        try:
            config_sha = _sha(_canonical(opened.get("observed_inference_config")))
        except (TypeError, ValueError, RecursionError):
            issue("OPEN_RECORD_CONTRADICTION", "slot_open.json")

    sequences: list[dict[str, Any]] = []
    highest = max(numbered, default=0)
    if highest and opened is None:
        issue("NUMBERED_ARTIFACT_BEFORE_OPEN")
    if numbered and sorted(numbered) != list(range(1, highest + 1)):
        issue("SEQUENCE_GAP")
    for sequence in range(1, highest + 1):
        kinds = numbered.get(sequence, set())
        fmt = lambda kind: f"{kind}-{sequence:06d}.{KIND_EXT[kind]}"
        request_name, start_name = fmt("request"), fmt("dispatch-start")
        response_name, return_name = fmt("response"), fmt("dispatch-return")
        decision_name, interruption_name = fmt("decision"), fmt("interruption")
        request = read(request_name)
        response = read(response_name)
        start = json_record(start_name) if "dispatch-start" in kinds else None
        returned = json_record(return_name) if "dispatch-return" in kinds else None
        decision = json_record(decision_name) if "decision" in kinds else None
        interruption = json_record(interruption_name) if "interruption" in kinds else None
        if "request" not in kinds:
            issue("REQUEST_MISSING", request_name)
        if "dispatch-start" in kinds and "request" not in kinds:
            issue("START_WITHOUT_REQUEST", start_name)
        if "response" in kinds and "dispatch-start" not in kinds:
            issue("RESPONSE_WITHOUT_START", response_name)
        if "dispatch-return" in kinds and "response" not in kinds:
            issue("RETURN_WITHOUT_RESPONSE", return_name)
        if "decision" in kinds and "dispatch-return" not in kinds:
            issue("DECISION_WITHOUT_RETURN", decision_name)
        if "interruption" in kinds and "dispatch-start" not in kinds:
            issue("INTERRUPTION_WITHOUT_START", interruption_name)
        if "interruption" in kinds and "response" in kinds:
            issue("INTERRUPTION_WITH_RESPONSE", interruption_name)
        if sequence < highest and "decision" not in kinds:
            issue("NEXT_SEQUENCE_BEFORE_DECISION", f"{sequence:06d}")
        if start is not None:
            if (start.get("schema_version") != DISPATCH_VERSION
                    or start.get("phase") != "pilot"
                    or start.get("eligible_for_main_analysis") is not False
                    or start.get("slot_id") != slot_id
                    or type(start.get("sequence")) is not int
                    or start.get("sequence") != sequence
                    or start.get("endpoint") != "/api/chat"
                    or start.get("request_path") != request_name
                    or request is None
                    or start.get("request_sha256") != _sha(request)
                    or type(start.get("request_length")) is not int
                    or start.get("request_length") != len(request)
                    or (opened is not None and (
                        start.get("observed_model") != opened.get("observed_model")
                        or start.get("inference_config_sha256") != config_sha))):
                issue("START_REQUEST_MISMATCH", start_name)
            if request is not None and opened is not None:
                try:
                    request_object = _strict_object(request)
                    config = opened["observed_inference_config"]
                    expected_options = {
                        "temperature": config["temperature"],
                        "num_ctx": config["num_ctx"],
                        "num_predict": config["max_output_tokens"],
                        "seed": opened["episode_seed"],
                    }
                    observed_model = opened["observed_model"]
                    if (request_object.get("model") != observed_model["name"]
                            or request_object.get("stream") is not False
                            or request_object.get("think") is not False
                            or _canonical(request_object.get("options")) !=
                            _canonical(expected_options)
                            or not isinstance(request_object.get("messages"), list)
                            or not request_object["messages"]
                            or not isinstance(request_object.get("format"), dict)):
                        issue("REQUEST_PROTOCOL_MISMATCH", request_name)
                except (UnicodeError, ValueError, KeyError, TypeError, RecursionError):
                    issue("REQUEST_PROTOCOL_MISMATCH", request_name)
        if returned is not None:
            if (returned.get("schema_version") != DISPATCH_VERSION
                    or returned.get("phase") != "pilot"
                    or returned.get("eligible_for_main_analysis") is not False
                    or returned.get("slot_id") != slot_id
                    or type(returned.get("sequence")) is not int
                    or returned.get("sequence") != sequence
                    or returned.get("response_path") != response_name
                    or response is None
                    or returned.get("response_sha256") != _sha(response)
                    or type(returned.get("response_length")) is not int
                    or returned.get("response_length") != len(response)):
                issue("RETURN_RESPONSE_MISMATCH", return_name)
        if interruption is not None:
            if (interruption.get("schema_version") != DISPATCH_VERSION
                    or interruption.get("phase") != "pilot"
                    or interruption.get("eligible_for_main_analysis") is not False
                    or interruption.get("slot_id") != slot_id
                    or type(interruption.get("sequence")) is not int
                    or interruption.get("sequence") != sequence
                    or interruption.get("reason") != "TRANSPORT_EXCEPTION"
                    or not isinstance(interruption.get("type"), str)
                    or not interruption["type"]
                    or not isinstance(interruption.get("message_sha256"), str)
                    or HEX64.fullmatch(interruption["message_sha256"]) is None):
                issue("INTERRUPTION_RECORD_CONTRADICTION", interruption_name)
        if decision is not None and response is not None:
            try:
                _check_response_envelope(response, "archived response")
                name, payload = _response_action(response)
                candidate = (_sha(_canonical(payload["candidate"]))
                             if name == "attempt" else None)
                if (type(decision.get("decision")) is not int
                        or decision.get("decision") != sequence
                        or type(decision.get("request_sequence")) is not int
                        or decision.get("request_sequence") != sequence
                        or decision.get("action") != name.upper()
                        or decision.get("submission") is not (name == "attempt")
                        or decision.get("candidate_sha256") != candidate
                        or decision.get("feedback_independently_verified") is not False
                        or ((decision.get("scripted_public_verdict") == "PASS"
                             or decision.get("scripted_public_verdict") == "FAIL")
                            is not (name == "attempt"))):
                    issue("DECISION_RESPONSE_MISMATCH", decision_name)
            except (ValueError, KeyError, TypeError, RuntimeError, RecursionError):
                issue("DECISION_RESPONSE_MISMATCH", decision_name)
        if (sequence < highest and decision is not None
                and isinstance(decision.get("action"), str)
                and decision["action"] in {"TERMINATE", "CLAIM"}):
            issue("NEXT_SEQUENCE_AFTER_TERMINAL_ACTION", decision_name)
        if "dispatch-return" in kinds:
            state, sent = ("RETURN_RECORDED" if "decision" not in kinds else "DECISION_RECORDED",
                           "RETURN_RECORDED")
        elif "response" in kinds:
            state, sent = "RESPONSE_WITHOUT_RETURN", "RESPONSE_ARCHIVED"
        elif "dispatch-start" in kinds:
            state, sent = "DISPATCH_OUTCOME_UNKNOWN", "UNKNOWN_AFTER_START"
        else:
            state, sent = "PRE_DISPATCH_INCOMPLETE", "NO_START_RECORD"
        sequences.append({"sequence": sequence, "state": state, "sent_status": sent,
                          "request_sha256": _sha(request) if request is not None else None,
                          "response_sha256": _sha(response) if response is not None else None})

    receipt_present = "slot_receipt.json" in files
    receipt_status = "absent"
    receipt = None
    if receipt_present:
        receipt = json_record("slot_receipt.json")
        if receipt is not None and receipt.get("schema_version") != DISPATCH_VERSION:
            issue("FINAL_RECEIPT_SCHEMA_CONTRADICTION", "slot_receipt.json")
        if receipt is not None and not issues:
            try:
                verified = verify_excluded_live_trace(root)
                receipt_status = "verified"
                receipt = verified
            except Exception:
                issue("FINAL_RECEIPT_VERIFICATION_FAILED", "slot_receipt.json")
                receipt_status = "unverifiable"
        else:
            receipt_status = "unverifiable"
    initialization_issues = {
        "INITIALIZATION_ARTIFACT_MISSING", "ARCHIVED_SOURCE_MISSING",
        "ARCHIVED_SOURCE_DIRECTORY_MISSING",
    }
    hard_issues = [entry for entry in issues if entry["code"] not in initialization_issues
                   or (opened is not None and entry["code"] in initialization_issues)]
    if hard_issues:
        classification, integrity = "ARTIFACT_CONTRADICTION", "failed"
    elif receipt_status == "verified":
        classification = ("CLOSED_COMPLETED" if receipt.get("status") ==
                          "COMPLETED_EXCLUDED_UNVERIFIED" else "CLOSED_INVALIDATED")
        integrity = "verified"
    elif receipt_present:
        classification, integrity = "FINAL_RECEIPT_UNVERIFIABLE", "failed"
    elif any(entry["code"] in initialization_issues for entry in issues):
        classification, integrity = "INITIALIZATION_PARTIAL", "incomplete"
    elif sequences:
        state = sequences[-1]["state"]
        classification = {
            "PRE_DISPATCH_INCOMPLETE": "PRE_DISPATCH_INCOMPLETE",
            "DISPATCH_OUTCOME_UNKNOWN": "DISPATCH_OUTCOME_UNKNOWN",
            "RESPONSE_WITHOUT_RETURN": "RESPONSE_WITHOUT_RETURN",
            "RETURN_RECORDED": "DECISION_PENDING",
            "DECISION_RECORDED": "FINAL_RECEIPT_MISSING",
        }[state]
        integrity = "incomplete"
    else:
        classification, integrity = "OPEN_NO_DISPATCH", "incomplete"

    return {
        "schema_version": AUDIT_VERSION, "phase": "pilot",
        "eligible_for_main_analysis": False, "main_dispatch_allowed": False,
        "slot_dir": str(root), "slot_id": slot_id,
        "classification": classification, "integrity": integrity,
        "sent_status": sequences[-1]["sent_status"] if sequences else "NO_START_RECORD",
        "sent_status_scope": "last_observed_sequence",
        "receipt_status": receipt_status,
        "recorded_receipt_status": receipt.get("status") if receipt_status == "verified" else None,
        "sequences": sequences, "issues": issues,
        "retry_allowed": False, "replacement_allowed": False,
        "process_liveness": "not_checked",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slot_dirs", nargs="+", type=Path,
                        help="existing excluded live-dispatch slot directories")
    args = parser.parse_args()
    reports = [audit_excluded_live_slot(path) for path in args.slot_dirs]
    print(json.dumps(reports[0] if len(reports) == 1 else reports,
                     ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if any(row["integrity"] == "failed" for row in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
