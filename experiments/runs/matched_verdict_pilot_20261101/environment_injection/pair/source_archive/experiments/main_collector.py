"""Fail-closed, scripted-only trace recorder for a proposed main slot.

This module has no provider client, evaluator, C5 fork, or main dispatch entry
point. It exercises the proposed six-decision archive contract with fixture
bytes. Every output is explicitly excluded from main analysis.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from experiments.main_schedule_consumer import (
    ExcludedScheduleError, check_schedule_bytes, schedule_kind, verify_fixture_schedule,
)


VERSION = "excluded-main-trace-scaffold-0.1.0"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
DECISION_CAP = 6


class MainTraceError(RuntimeError):
    """A scripted trace fails its frozen, excluded recording contract."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _relative_source(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\\" in name:
        raise MainTraceError("source path must be a safe repository-relative POSIX path")
    part = PurePosixPath(name)
    if part.is_absolute() or any(piece in {"", ".", ".."} for piece in name.split("/")):
        raise MainTraceError("source path escapes source root")
    target = root.joinpath(*part.parts)
    if not target.resolve().is_relative_to(root) or any(
        ancestor.is_symlink() for ancestor in (target, *target.parents) if ancestor != root
        and ancestor.is_relative_to(root)
    ):
        raise MainTraceError("source path escapes source root or crosses a symlink")
    return target


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MainTraceError("duplicate JSON key in fixture record")
        result[key] = value
    return result


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeDecodeError) as exc:
        raise MainTraceError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise MainTraceError(f"{label} must be a JSON object")
    return value


def _response_action(data: bytes) -> tuple[str, dict[str, Any]]:
    response = _json_object(data, "fixture response")
    message = response.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise MainTraceError("fixture response lacks exact message content")
    action = _json_object(message["content"].encode("utf-8"), "fixture action")
    if set(action) != {"action", "payload"} or not isinstance(action["payload"], dict):
        raise MainTraceError("fixture action envelope is malformed")
    name, payload = action["action"], action["payload"]
    if name not in {"inspect", "attempt", "terminate", "claim", "security_check"}:
        raise MainTraceError("fixture action is unsupported")
    if name in {"inspect", "terminate", "security_check"} and payload:
        raise MainTraceError("fixture action has unexpected payload")
    if name == "attempt" and (set(payload) != {"candidate"}
                              or not isinstance(payload["candidate"], dict)):
        raise MainTraceError("fixture attempt lacks a reconstructable candidate")
    if name == "claim" and (set(payload) != {"status"}
                            or payload["status"] not in {"success", "non_success", "unknown"}):
        raise MainTraceError("fixture claim is malformed")
    return name, payload


class ExcludedMainTrace:
    """Record one proposed slot from scripted bytes, never contact a model.

    The caller must archive each request *before* supplying its fixture response.
    This order is enforced within the recorder, but a future live adapter still
    needs separate proof that its network call occurs after the archive fsync.
    """

    def __init__(self, *, plan: Mapping[str, Any], slot_id: str,
                 source_root: Path, output_dir: Path,
                 observed_model: Mapping[str, str],
                 observed_inference_config: Mapping[str, Any],
                 schedule_path: Path | None = None) -> None:
        try:
            schedule_type, schedule_raw, schedule_file_sha256 = verify_fixture_schedule(
                plan, source_root=source_root, schedule_path=schedule_path)
        except ExcludedScheduleError as exc:
            raise MainTraceError(str(exc)) from exc
        if not isinstance(slot_id, str) or SAFE_ID.fullmatch(slot_id) is None:
            raise MainTraceError("unsafe slot ID")
        slots = plan.get("slots")
        if not isinstance(slots, list):
            raise MainTraceError("plan slots are missing")
        matching = [row for row in slots if isinstance(row, dict) and row.get("slot_id") == slot_id]
        if len(matching) != 1:
            raise MainTraceError("slot ID must occur exactly once in the plan")
        slot = matching[0]
        models = plan.get("models")
        if (not isinstance(models, list) or len(models) != 1
                or not isinstance(models[0], dict)
                or dict(observed_model) != models[0]
                or slot.get("model") != models[0].get("name")
                or slot.get("model_digest") != models[0].get("digest")
                or not isinstance(slot.get("model_digest"), str)
                or HEX64.fullmatch(slot["model_digest"]) is None):
            raise MainTraceError("observed model name/digest differs from planned slot")
        config = plan.get("inference_config")
        if (not isinstance(config, dict) or config.get("max_steps") != DECISION_CAP
                or _canonical(config) != _canonical(dict(observed_inference_config))
                or not isinstance(slot.get("episode_seed"), int)
                or type(slot["episode_seed"]) is not int):
            raise MainTraceError("observed inference configuration or six-decision cap differs")
        source_hashes = plan.get("source_file_sha256s")
        if not isinstance(source_hashes, dict) or not source_hashes:
            raise MainTraceError("plan has no frozen source inventory")
        for kind in ("task", "proof"):
            name, digest = slot.get(f"{kind}_path"), slot.get(f"{kind}_sha256")
            if not isinstance(name, str) or source_hashes.get(name) != digest:
                raise MainTraceError(f"slot {kind} is not bound to source inventory")
        source_root = Path(source_root).resolve()
        verified_sources: list[tuple[str, bytes, str]] = []
        for name, expected in sorted(source_hashes.items()):
            if not isinstance(expected, str) or HEX64.fullmatch(expected) is None:
                raise MainTraceError("source inventory has an invalid SHA-256")
            try:
                raw = _relative_source(source_root, name).read_bytes()
            except OSError as exc:
                raise MainTraceError(f"frozen source is unreadable: {name}") from exc
            if _sha(raw) != expected:
                raise MainTraceError(f"frozen source hash differs: {name}")
            verified_sources.append((name, raw, expected))
        self.output_dir = Path(output_dir)
        if self.output_dir.exists():
            raise MainTraceError("slot output already exists; no overwrite or retry")
        self.output_dir.mkdir(mode=0o700, parents=True)
        os.chmod(self.output_dir, 0o700)
        self.source_root = source_root
        self.source_hashes = dict(source_hashes)
        self.slot = dict(slot)
        self.config = dict(config)
        self.plan_sha256 = _sha(_canonical(plan))
        self.schedule_type = schedule_type
        self.schedule_file_sha256 = schedule_file_sha256
        self.requests: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []
        self.pending: int | None = None
        self.awaiting_action = False
        self.terminal = False
        self.final_receipt: dict[str, Any] | None = None
        for name, raw, _ in verified_sources:
            _write_once(self.output_dir / "source_archive" / name, raw)
        _write_once(self.output_dir / "plan_snapshot.json", _canonical(plan))
        if schedule_raw is not None:
            _write_once(self.output_dir / "schedule_source.json", schedule_raw)
        _write_once(self.output_dir / "source_inventory.json", _canonical({
            "schema_version": VERSION, "source_file_sha256s": self.source_hashes,
        }) + b"\n")
        _write_once(self.output_dir / "slot_open.json", _canonical({
            "schema_version": VERSION, "phase": "pilot",
            "status": "EXCLUDED_SCRIPTED_MAIN_SCAFFOLD",
            "eligible_for_main_analysis": False, "main_dispatch_allowed": False,
            "slot_id": slot_id, "plan_sha256": self.plan_sha256,
            "schedule_type": self.schedule_type,
            "schedule_file_sha256": self.schedule_file_sha256,
            "model": models[0], "inference_config": self.config,
            "episode_seed": slot["episode_seed"],
        }) + b"\n")

    def archive_request_before_fixture_response(self, request_bytes: bytes,
                                                *, endpoint: str = "/api/chat") -> int:
        if self.terminal or self.final_receipt is not None or self.pending is not None:
            raise MainTraceError("previous fixture decision is unfinished or slot is closed")
        if len(self.actions) >= DECISION_CAP:
            raise MainTraceError("six-decision horizon is exhausted")
        if not isinstance(request_bytes, bytes) or not request_bytes:
            raise MainTraceError("exact nonempty request bytes are required")
        if endpoint != "/api/chat":
            raise MainTraceError("fixture endpoint differs from frozen protocol")
        if self._source_post() != self.source_hashes:
            raise MainTraceError("source changed before fixture request archive")
        request = _json_object(request_bytes, "fixture request")
        options = request.get("options")
        expected_options = {
            "temperature": self.config["temperature"],
            "num_ctx": self.config["num_ctx"],
            "num_predict": self.config["max_output_tokens"],
            "seed": self.slot["episode_seed"],
        }
        if (request.get("model") != self.slot["model"] or request.get("stream") is not False
                or request.get("think") is not False or options != expected_options
                or not isinstance(request.get("messages"), list)
                or not request["messages"] or not isinstance(request.get("format"), dict)):
            raise MainTraceError("fixture request differs from model, seed or frozen options")
        sequence = len(self.requests) + 1
        path = f"request-{sequence:06d}.json"
        _write_once(self.output_dir / path, request_bytes)
        self.requests.append({"sequence": sequence, "request_path": path,
                              "request_sha256": _sha(request_bytes),
                              "response_path": None, "response_sha256": None})
        self.pending = sequence
        self.awaiting_action = False
        return sequence

    def record_fixture_response(self, response_bytes: bytes, *, sequence: int) -> None:
        if self.final_receipt is not None or self.pending != sequence or self.awaiting_action:
            raise MainTraceError("fixture response has no matching archived request")
        if not isinstance(response_bytes, bytes) or not response_bytes:
            raise MainTraceError("exact nonempty response bytes are required")
        path = f"response-{sequence:06d}.json"
        _write_once(self.output_dir / path, response_bytes)
        self.requests[-1].update(response_path=path, response_sha256=_sha(response_bytes))
        # Preserve even a malformed provider response; parsing failure leaves
        # this request pending so the scheduled slot must be invalidated.
        _response_action(response_bytes)
        self.awaiting_action = True

    def record_decision(self, *, scripted_public_verdict: str | None = None) -> dict[str, Any]:
        if self.final_receipt is not None or self.pending is None or not self.awaiting_action:
            raise MainTraceError("decision has no matching archived fixture response")
        raw = (self.output_dir / self.requests[-1]["response_path"]).read_bytes()
        action, payload = _response_action(raw)
        if action == "attempt":
            if scripted_public_verdict not in {"PASS", "FAIL"}:
                raise MainTraceError("scripted attempt requires an explicit public verdict")
        elif scripted_public_verdict is not None:
            raise MainTraceError("only scripted attempts may carry a public verdict")
        decision = {
            "decision": len(self.actions) + 1,
            "request_sequence": self.pending,
            "action": action.upper(),
            "submission": action == "attempt",
            "candidate_sha256": _sha(_canonical(payload["candidate"])) if action == "attempt" else None,
            "scripted_public_verdict": scripted_public_verdict,
            "fixture_feedback_unverified": action == "attempt",
        }
        self.actions.append(decision)
        self.pending = None
        self.awaiting_action = False
        if action in {"terminate", "claim"}:
            self.terminal = True
        return dict(decision)

    def finish(self, *, timeout: bool = False) -> dict[str, Any]:
        if self.final_receipt is not None:
            raise MainTraceError("slot already closed")
        if self.pending is not None:
            raise MainTraceError("pending request requires explicit invalidation")
        if timeout and self.terminal:
            raise MainTraceError("timeout cannot overwrite an observed voluntary stop")
        if timeout and not self.requests:
            raise MainTraceError("timeout before any request requires invalidation")
        if timeout and len(self.actions) == DECISION_CAP:
            raise MainTraceError("six completed decisions are a budget stop, not a timeout")
        if not timeout and not self.terminal and len(self.actions) != DECISION_CAP:
            raise MainTraceError("slot cannot finish before six decisions without a stop")
        source_post = self._source_post()
        if source_post != self.source_hashes:
            return self.invalidate("SOURCE_DRIFT_OR_UNAVAILABLE", source_post=source_post)
        stop = "TIMEOUT" if timeout else "VOLUNTARY" if self.terminal else "BUDGET"
        return self._close("VALID_EXCLUDED_SCRIPTED", stop, None, source_post)

    def invalidate(self, reason: str, *, source_post: dict[str, str | None] | None = None
                   ) -> dict[str, Any]:
        if self.final_receipt is not None:
            raise MainTraceError("slot already closed")
        if not isinstance(reason, str) or SAFE_ID.fullmatch(reason) is None:
            raise MainTraceError("invalid structured invalidation reason")
        return self._close("INVALIDATED_EXCLUDED_SCRIPTED", "INFRASTRUCTURE_ABORT",
                           reason, self._source_post() if source_post is None else source_post)

    def _source_post(self) -> dict[str, str | None]:
        observed: dict[str, str | None] = {}
        for name in sorted(self.source_hashes):
            try:
                observed[name] = _sha(_relative_source(self.source_root, name).read_bytes())
            except (OSError, MainTraceError):
                observed[name] = None
        return observed

    def _close(self, status: str, stop: str, reason: str | None,
               source_post: dict[str, str | None]) -> dict[str, Any]:
        decisions = len(self.actions)
        row = {
            "slot_id": self.slot["slot_id"], "status": status,
            "invalidated_reason": reason, "replacement_count": 0,
            "eligible_for_main_analysis": False,
            "c5_onset_status": "NOT_ASSESSED_BY_SCRIPTED_SCAFFOLD",
        }
        receipt = {
            "schema_version": VERSION, "phase": "pilot", "status": status,
            "eligible_for_main_analysis": False, "main_dispatch_allowed": False,
            "model_calls": 0, "slot_id": self.slot["slot_id"],
            "plan_sha256": self.plan_sha256, "model_digest": self.slot["model_digest"],
            "schedule_type": self.schedule_type,
            "schedule_file_sha256": self.schedule_file_sha256,
            "inference_config": self.config, "source_file_sha256s": self.source_hashes,
            "source_post_sha256s": source_post,
            "source_unchanged": source_post == self.source_hashes,
            "request_response_archive": self.requests,
            "actions": self.actions, "decision_count": decisions,
            "submission_count": sum(row["submission"] for row in self.actions),
            "remaining_decisions": DECISION_CAP - decisions,
            "stop_reason": stop,
            "early_voluntary_stop": stop == "VOLUNTARY" and decisions < DECISION_CAP,
            "budget_edge_voluntary_stop": stop == "VOLUNTARY" and decisions == DECISION_CAP,
            "invalidated_reason": reason, "slot_ledger_row": row,
            "fixture_feedback_independently_verified": False,
        }
        _write_once(self.output_dir / "slot_receipt.json", _canonical(receipt) + b"\n")
        self.final_receipt = receipt
        return json.loads(_canonical(receipt))


def verify_excluded_trace(output_dir: Path) -> dict[str, Any]:
    """Rehash the archived fixture bytes and check ledger accounting."""
    root = Path(output_dir)
    opened = _json_object((root / "slot_open.json").read_bytes(), "slot open")
    receipt = _json_object((root / "slot_receipt.json").read_bytes(), "slot receipt")
    inventory = _json_object((root / "source_inventory.json").read_bytes(), "source inventory")
    if (opened.get("phase") != "pilot" or receipt.get("phase") != "pilot"
            or opened.get("eligible_for_main_analysis") is not False
            or receipt.get("eligible_for_main_analysis") is not False
            or receipt.get("main_dispatch_allowed") is not False
            or receipt.get("model_calls") != 0
            or opened.get("plan_sha256") != receipt.get("plan_sha256")
            or inventory.get("source_file_sha256s") != receipt.get("source_file_sha256s")):
        raise MainTraceError("excluded fixture identity is inconsistent")
    if _sha((root / "plan_snapshot.json").read_bytes()) != receipt.get("plan_sha256"):
        raise MainTraceError("plan snapshot differs from opening receipt")
    plan = _json_object((root / "plan_snapshot.json").read_bytes(), "plan snapshot")
    try:
        expected_type = schedule_kind(plan)
        schedule_file = root / "schedule_source.json"
        if expected_type == "final-v0.3":
            if schedule_file.is_symlink() or not schedule_file.is_file():
                raise MainTraceError("final schedule source is missing or redirected")
            saved_schedule_sha = check_schedule_bytes(plan, schedule_file.read_bytes())
        else:
            if schedule_file.exists() or schedule_file.is_symlink():
                raise MainTraceError("proposed fixture has an unexpected final schedule source")
            saved_schedule_sha = None
    except ExcludedScheduleError as exc:
        raise MainTraceError(str(exc)) from exc
    if (opened.get("schedule_type", expected_type) != expected_type
            or receipt.get("schedule_type", expected_type) != expected_type
            or opened.get("schedule_file_sha256") != saved_schedule_sha
            or receipt.get("schedule_file_sha256") != saved_schedule_sha):
        raise MainTraceError("schedule identity differs from archived exact bytes")
    source_hashes = receipt["source_file_sha256s"]
    for name, expected in source_hashes.items():
        if _sha(_relative_source((root / "source_archive").resolve(), name).read_bytes()) != expected:
            raise MainTraceError(f"archived source changed: {name}")
    requests, actions = receipt.get("request_response_archive"), receipt.get("actions")
    if not isinstance(requests, list) or not isinstance(actions, list):
        raise MainTraceError("fixture request or action ledger is missing")
    invalidated = receipt.get("status") == "INVALIDATED_EXCLUDED_SCRIPTED"
    if (receipt.get("status") not in {"VALID_EXCLUDED_SCRIPTED", "INVALIDATED_EXCLUDED_SCRIPTED"}
            or invalidated is not (receipt.get("invalidated_reason") is not None)
            or len(requests) < len(actions) or len(requests) > len(actions) + int(invalidated)):
        raise MainTraceError("slot completion or invalidation state is inconsistent")
    for sequence, record in enumerate(requests, 1):
        if record.get("sequence") != sequence:
            raise MainTraceError("noncontiguous request sequence")
        for kind in ("request", "response"):
            path, digest = record.get(f"{kind}_path"), record.get(f"{kind}_sha256")
            if path is None:
                if kind == "response" and invalidated and digest is None and sequence == len(requests):
                    continue
                raise MainTraceError("completed fixture lacks response")
            if path != f"{kind}-{sequence:06d}.json" or _sha((root / path).read_bytes()) != digest:
                raise MainTraceError(f"archived {kind} bytes changed")
        request = _json_object((root / record["request_path"]).read_bytes(), "archived request")
        config = receipt["inference_config"]
        if (request.get("model") != opened["model"]["name"]
                or request.get("stream") is not False or request.get("think") is not False
                or request.get("options") != {
                    "temperature": config["temperature"], "num_ctx": config["num_ctx"],
                    "num_predict": config["max_output_tokens"], "seed": opened["episode_seed"],
                }):
            raise MainTraceError("archived request differs from frozen model/options")
    if (receipt.get("decision_count") != len(actions) or len(actions) > DECISION_CAP
            or receipt.get("submission_count") != sum(row.get("submission") is True for row in actions)
            or receipt.get("remaining_decisions") != DECISION_CAP - len(actions)
            or receipt.get("slot_ledger_row", {}).get("replacement_count") != 0):
        raise MainTraceError("decision or slot ledger accounting differs")
    stop = receipt.get("stop_reason")
    last_action = actions[-1].get("action") if actions else None
    if (not invalidated and (
        (stop == "BUDGET" and (len(actions) != DECISION_CAP or last_action in {"TERMINATE", "CLAIM"}))
        or (stop == "VOLUNTARY" and last_action not in {"TERMINATE", "CLAIM"})
        or (stop == "TIMEOUT" and (len(actions) >= DECISION_CAP or not requests))
        or stop not in {"BUDGET", "VOLUNTARY", "TIMEOUT"}
        or receipt.get("source_unchanged") is not True
    )) or (invalidated and stop != "INFRASTRUCTURE_ABORT"):
        raise MainTraceError("terminal cause contradicts the archived decisions")
    if (receipt.get("early_voluntary_stop") is not (stop == "VOLUNTARY" and len(actions) < DECISION_CAP)
            or receipt.get("budget_edge_voluntary_stop") is not (stop == "VOLUNTARY" and len(actions) == DECISION_CAP)
            or receipt.get("slot_ledger_row", {}).get("status") != receipt.get("status")
            or receipt.get("slot_ledger_row", {}).get("invalidated_reason") != receipt.get("invalidated_reason")
            or receipt.get("source_unchanged") is not (
                receipt.get("source_post_sha256s") == source_hashes)):
        raise MainTraceError("stop or invalidation ledger accounting differs")
    for index, row in enumerate(actions, 1):
        if row.get("decision") != index or row.get("request_sequence") != index:
            raise MainTraceError("action sequence differs from requests")
        response = (root / requests[index - 1]["response_path"]).read_bytes()
        name, payload = _response_action(response)
        if (row.get("action") != name.upper() or row.get("submission") is not (name == "attempt")
                or row.get("candidate_sha256") != (
                    _sha(_canonical(payload["candidate"])) if name == "attempt" else None)):
            raise MainTraceError("action differs from archived response")
    return receipt
