"""Private, excluded-only live-dispatch recorder for a proposed main slot.

Transport injection makes the request/response boundary testable without a
model. This is not a main collector: it has no evaluator, independent oracle,
retrieval provider, C5 fork, or path that emits main-eligible observations.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Protocol

from experiments.main_collector import (
    DECISION_CAP, HEX64, SAFE_ID, MainTraceError, _canonical, _json_object,
    _relative_source, _response_action, _sha,
)


VERSION = "excluded-live-dispatch-0.1.0"


class LiveDispatchError(MainTraceError):
    """The excluded dispatch slot failed its byte-ordering contract."""


class ByteTransport(Protocol):
    """An injected byte transport; identity must be observed before each send."""

    def model_identity(self) -> Mapping[str, str]: ...

    def send(self, request_bytes: bytes, *, endpoint: str) -> bytes: ...


def _write_once_durable(path: Path, raw: bytes) -> None:
    """Persist file content and directory entry before returning to the caller."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not isinstance(raw, bytes):
        raise TypeError("archive content must be bytes")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _record(root: Path, name: str, value: Mapping[str, Any]) -> None:
    _write_once_durable(root / name, _canonical(dict(value)) + b"\n")


def _strict_json(data: bytes, label: str) -> Any:
    def reject_constant(value: str) -> None:
        raise LiveDispatchError(f"{label} contains non-JSON constant {value}")

    try:
        return json.loads(data, parse_constant=reject_constant)
    except (ValueError, UnicodeDecodeError) as exc:
        raise LiveDispatchError(f"{label} is not strict UTF-8 JSON") from exc


def _check_response_envelope(raw: bytes, label: str) -> None:
    """Reject partial Ollama chunks after the recorder has saved their bytes."""
    outer = _strict_json(raw, label)
    if isinstance(outer, dict) and "done" in outer and outer["done"] is not True:
        raise LiveDispatchError(f"{label} is not a completed Ollama response")
    if isinstance(outer, dict) and isinstance(outer.get("message"), dict):
        content = outer["message"].get("content")
        if isinstance(content, str):
            _strict_json(content.encode("utf-8"), f"{label} action")


class ExcludedLiveDispatch:
    """One no-retry pilot slot with a strict archive-before-send boundary.

    ``dispatch`` saves exact request bytes and a pre-dispatch record, both
    fsynced, before it calls ``transport.send``. The returned response is saved
    before parsing. A transport/protocol/archive failure invalidates the slot.
    Each parsed response consumes one decision only after ``record_decision``;
    an attempt needs explicit, still-unverified public feedback. PASS does not
    end the six-decision horizon.
    """

    def __init__(self, *, plan: Mapping[str, Any], slot_id: str,
                 source_root: Path, output_dir: Path,
                 observed_inference_config: Mapping[str, Any],
                 transport: ByteTransport) -> None:
        if (plan.get("phase") != "main" or plan.get("status") != "PROPOSED_MAIN_UNGATED"
                or plan.get("eligible_for_main_analysis") is not False
                or plan.get("main_execution_implemented") is not False):
            raise LiveDispatchError("only an ungated proposed plan may be rehearsed")
        if not isinstance(slot_id, str) or SAFE_ID.fullmatch(slot_id) is None:
            raise LiveDispatchError("unsafe slot ID")
        slots = plan.get("slots")
        matching = ([row for row in slots if isinstance(row, dict)
                     and row.get("slot_id") == slot_id] if isinstance(slots, list) else [])
        if len(matching) != 1:
            raise LiveDispatchError("slot ID must occur exactly once")
        slot = matching[0]
        models = plan.get("models")
        if (not isinstance(models, list) or len(models) != 1
                or not isinstance(models[0], dict)
                or slot.get("model") != models[0].get("name")
                or slot.get("model_digest") != models[0].get("digest")
                or not isinstance(slot.get("model_digest"), str)
                or HEX64.fullmatch(slot["model_digest"]) is None):
            raise LiveDispatchError("planned model identity is malformed")
        config = plan.get("inference_config")
        if (not isinstance(config, dict) or config.get("max_steps") != DECISION_CAP
                or _canonical(config) != _canonical(dict(observed_inference_config))
                or type(slot.get("episode_seed")) is not int):
            raise LiveDispatchError("inference configuration or six-decision cap differs")
        if not callable(getattr(transport, "model_identity", None)) or not callable(
            getattr(transport, "send", None)
        ):
            raise LiveDispatchError("transport lacks model identity or byte send")
        try:
            observed_model = dict(transport.model_identity())
        except Exception as exc:
            raise LiveDispatchError("cannot observe transport model identity") from exc
        if observed_model != models[0]:
            raise LiveDispatchError("observed transport model differs from planned model")
        source_hashes = plan.get("source_file_sha256s")
        if not isinstance(source_hashes, dict) or not source_hashes:
            raise LiveDispatchError("plan lacks a source inventory")
        for kind in ("task", "proof"):
            name, digest = slot.get(f"{kind}_path"), slot.get(f"{kind}_sha256")
            if not isinstance(name, str) or source_hashes.get(name) != digest:
                raise LiveDispatchError(f"slot {kind} is not bound to source inventory")
        source_root = Path(source_root).resolve()
        verified_sources = []
        for name, expected in sorted(source_hashes.items()):
            if not isinstance(expected, str) or HEX64.fullmatch(expected) is None:
                raise LiveDispatchError("source inventory has an invalid SHA-256")
            try:
                raw = _relative_source(source_root, name).read_bytes()
            except (OSError, MainTraceError) as exc:
                raise LiveDispatchError(f"frozen source is unreadable: {name}") from exc
            if _sha(raw) != expected:
                raise LiveDispatchError(f"frozen source changed: {name}")
            verified_sources.append((name, raw))
        self.output_dir = Path(output_dir)
        if self.output_dir.exists():
            raise LiveDispatchError("slot output exists; no overwrite or replacement")
        self.output_dir.mkdir(mode=0o700, parents=True)
        os.chmod(self.output_dir, 0o700)
        self.source_root = source_root
        self.source_hashes = dict(source_hashes)
        self.slot = dict(slot)
        self.config = dict(config)
        self.model = dict(observed_model)
        self.plan_sha256 = _sha(_canonical(plan))
        self.transport = transport
        self.calls: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []
        self.pending: int | None = None
        self.terminal = False
        self.closed = False
        self.dispatch_attempts = 0
        self.failure: dict[str, Any] | None = None
        for name, raw in verified_sources:
            _write_once_durable(self.output_dir / "source_archive" / name, raw)
        _write_once_durable(self.output_dir / "plan_snapshot.json", _canonical(plan))
        _record(self.output_dir, "source_inventory.json", {
            "schema_version": VERSION, "source_file_sha256s": self.source_hashes,
        })
        _record(self.output_dir, "slot_open.json", {
            "schema_version": VERSION, "phase": "pilot",
            "status": "EXCLUDED_LIVE_DISPATCH_OPEN",
            "eligible_for_main_analysis": False, "main_dispatch_allowed": False,
            "slot_id": slot_id, "plan_sha256": self.plan_sha256,
            "observed_model": self.model, "observed_inference_config": self.config,
            "episode_seed": slot["episode_seed"], "replacement_count": 0,
        })

    def _source_post(self) -> dict[str, str | None]:
        observed: dict[str, str | None] = {}
        for name in sorted(self.source_hashes):
            try:
                observed[name] = _sha(_relative_source(self.source_root, name).read_bytes())
            except (OSError, MainTraceError):
                observed[name] = None
        return observed

    def _check_request(self, raw: bytes, endpoint: str) -> None:
        if not isinstance(raw, bytes) or not raw:
            raise LiveDispatchError("exact nonempty request bytes are required")
        if endpoint != "/api/chat":
            raise LiveDispatchError("only the frozen /api/chat endpoint is supported")
        _strict_json(raw, "live request")
        request = _json_object(raw, "live request")
        expected_options = {
            "temperature": self.config["temperature"],
            "num_ctx": self.config["num_ctx"],
            "num_predict": self.config["max_output_tokens"],
            "seed": self.slot["episode_seed"],
        }
        if (request.get("model") != self.slot["model"] or request.get("stream") is not False
                or request.get("think") is not False
                or _canonical(request.get("options")) != _canonical(expected_options)
                or not isinstance(request.get("messages"), list) or not request["messages"]
                or not isinstance(request.get("format"), dict)):
            raise LiveDispatchError("request differs from frozen model, seed or options")

    def dispatch(self, request_bytes: bytes, *, endpoint: str = "/api/chat") -> int:
        if self.closed or self.terminal or self.pending is not None:
            raise LiveDispatchError("slot is closed or a decision is unfinished")
        if len(self.actions) >= DECISION_CAP:
            raise LiveDispatchError("six-decision horizon is exhausted")
        try:
            self._check_request(request_bytes, endpoint)
        except (LiveDispatchError, MainTraceError) as exc:
            self.invalidate("REQUEST_PROTOCOL_FAILURE")
            raise LiveDispatchError("request rejected before dispatch; slot invalidated") from exc
        if self._source_post() != self.source_hashes:
            self.invalidate("SOURCE_DRIFT_BEFORE_DISPATCH")
            raise LiveDispatchError("source changed before dispatch; slot invalidated")
        try:
            observed_model = dict(self.transport.model_identity())
        except BaseException as exc:
            self.invalidate("MODEL_IDENTITY_UNAVAILABLE")
            if not isinstance(exc, Exception):
                raise
            raise LiveDispatchError("model identity unavailable; slot invalidated") from exc
        if observed_model != self.model:
            self.invalidate("MODEL_IDENTITY_DRIFT")
            raise LiveDispatchError("model identity changed; slot invalidated")
        sequence = len(self.calls) + 1
        request_path = f"request-{sequence:06d}.bin"
        start_path = f"dispatch-start-{sequence:06d}.json"
        row = {
            "sequence": sequence, "endpoint": endpoint,
            "request_path": request_path, "request_sha256": _sha(request_bytes),
            "request_length": len(request_bytes), "start_path": start_path,
            "response_path": None, "response_sha256": None, "response_length": None,
            "return_path": None,
        }
        try:
            _write_once_durable(self.output_dir / request_path, request_bytes)
            _record(self.output_dir, start_path, {
                "schema_version": VERSION, "phase": "pilot",
                "eligible_for_main_analysis": False,
                "slot_id": self.slot["slot_id"], "sequence": sequence,
                "endpoint": endpoint, "request_path": request_path,
                "request_sha256": row["request_sha256"],
                "request_length": row["request_length"],
                "observed_model": observed_model,
                "inference_config_sha256": _sha(_canonical(self.config)),
            })
        except BaseException as exc:
            self.failure = {"sequence": sequence, "type": type(exc).__name__,
                            "request_sha256": row["request_sha256"],
                            "request_length": row["request_length"]}
            self.invalidate("REQUEST_ARCHIVE_FAILURE")
            if not isinstance(exc, Exception):
                raise
            raise LiveDispatchError("request archive failed before transport send") from exc
        self.calls.append(row)
        self.pending = sequence
        self.dispatch_attempts += 1
        try:
            response = self.transport.send(request_bytes, endpoint=endpoint)
        except BaseException as exc:
            self.failure = {
                "sequence": sequence, "type": type(exc).__name__,
                "message_sha256": hashlib.sha256(str(exc).encode(
                    "utf-8", errors="replace")).hexdigest(),
            }
            try:
                _record(self.output_dir, f"interruption-{sequence:06d}.json", {
                    "schema_version": VERSION, "phase": "pilot",
                    "eligible_for_main_analysis": False,
                    "slot_id": self.slot["slot_id"], "reason": "TRANSPORT_EXCEPTION",
                    **self.failure,
                })
            except BaseException as archive_exc:
                self.failure["interruption_archive_error_type"] = type(archive_exc).__name__
            self.invalidate("TRANSPORT_EXCEPTION")
            raise
        if not isinstance(response, bytes):
            self.invalidate("NON_BYTES_RESPONSE")
            raise LiveDispatchError("transport returned non-byte response; slot invalidated")
        response_path = f"response-{sequence:06d}.bin"
        return_path = f"dispatch-return-{sequence:06d}.json"
        try:
            _write_once_durable(self.output_dir / response_path, response)
            row.update(response_path=response_path,
                       response_sha256=_sha(response), response_length=len(response))
            _record(self.output_dir, return_path, {
                "schema_version": VERSION, "phase": "pilot",
                "eligible_for_main_analysis": False,
                "slot_id": self.slot["slot_id"], "sequence": sequence,
                "response_path": response_path, "response_sha256": row["response_sha256"],
                "response_length": row["response_length"],
            })
            row["return_path"] = return_path
        except BaseException as exc:
            self.failure = {"sequence": sequence, "type": type(exc).__name__,
                            "response_sha256": _sha(response),
                            "response_length": len(response)}
            self.invalidate("RESPONSE_ARCHIVE_FAILURE")
            if not isinstance(exc, Exception):
                raise
            raise LiveDispatchError("response archive failed; slot invalidated") from exc
        try:
            _check_response_envelope(response, "live response")
            _, payload = _response_action(response)
            _canonical(payload)
        except (MainTraceError, ValueError) as exc:
            self.invalidate("RESPONSE_PROTOCOL_FAILURE")
            raise LiveDispatchError("response protocol failed; raw bytes retained") from exc
        return sequence

    def record_decision(self, *, scripted_public_verdict: str | None = None) -> dict[str, Any]:
        if self.closed or self.pending is None:
            raise LiveDispatchError("no completed response awaits a decision")
        row = self.calls[self.pending - 1]
        if row["response_path"] is None:
            raise LiveDispatchError("response bytes were not archived")
        try:
            response = (self.output_dir / row["response_path"]).read_bytes()
            if _sha(response) != row["response_sha256"]:
                raise LiveDispatchError("response hash changed")
            _check_response_envelope(response, "archived response")
            name, payload = _response_action(response)
            _canonical(payload)
        except (OSError, MainTraceError, ValueError) as exc:
            self.invalidate("RESPONSE_ARCHIVE_TAMPER")
            raise LiveDispatchError("response archive changed; slot invalidated") from exc
        if name == "attempt":
            if scripted_public_verdict not in {"PASS", "FAIL"}:
                raise LiveDispatchError("attempt needs explicit unverified public verdict")
        elif scripted_public_verdict is not None:
            raise LiveDispatchError("only an attempt may carry a public verdict")
        decision = {
            "decision": len(self.actions) + 1, "request_sequence": self.pending,
            "action": name.upper(), "submission": name == "attempt",
            "candidate_sha256": _sha(_canonical(payload["candidate"]))
                if name == "attempt" else None,
            "scripted_public_verdict": scripted_public_verdict,
            "feedback_independently_verified": False,
        }
        try:
            _record(self.output_dir, f"decision-{self.pending:06d}.json", decision)
        except BaseException as exc:
            self.invalidate("DECISION_ARCHIVE_FAILURE")
            if not isinstance(exc, Exception):
                raise
            raise LiveDispatchError("decision archive failed; slot invalidated") from exc
        self.actions.append(decision)
        self.pending = None
        if name in {"terminate", "claim"}:
            self.terminal = True
        return dict(decision)

    def finish(self, *, timeout: bool = False) -> dict[str, Any]:
        if self.closed:
            raise LiveDispatchError("slot already closed")
        if self.pending is not None:
            raise LiveDispatchError("unfinished decision requires invalidation")
        if timeout and (self.terminal or len(self.actions) == DECISION_CAP or not self.calls):
            raise LiveDispatchError("timeout contradicts observed stopping state")
        if not timeout and not self.terminal and len(self.actions) != DECISION_CAP:
            raise LiveDispatchError("slot cannot finish before six decisions without stop")
        source_post = self._source_post()
        if source_post != self.source_hashes:
            return self.invalidate("SOURCE_DRIFT_AFTER_DISPATCH")
        stop = "TIMEOUT" if timeout else "VOLUNTARY" if self.terminal else "BUDGET"
        return self._close("COMPLETED_EXCLUDED_UNVERIFIED", stop, None, source_post)

    def invalidate(self, reason: str) -> dict[str, Any]:
        if self.closed:
            raise LiveDispatchError("slot already closed")
        if not isinstance(reason, str) or SAFE_ID.fullmatch(reason) is None:
            raise LiveDispatchError("invalid structured invalidation reason")
        return self._close("INVALIDATED_EXCLUDED_LIVE", "INFRASTRUCTURE_ABORT",
                           reason, self._source_post())

    def _close(self, status: str, stop: str, reason: str | None,
               source_post: dict[str, str | None]) -> dict[str, Any]:
        referenced_raw = {
            value for call in self.calls for value in
            (call["request_path"], call["response_path"]) if value is not None
        }
        orphaned_raw = [
            {"path": path.name, "sha256": _sha(path.read_bytes()),
             "length": path.stat().st_size}
            for pattern in ("request-*.bin", "response-*.bin")
            for path in sorted(self.output_dir.glob(pattern))
            if path.name not in referenced_raw
        ]
        receipt = {
            "schema_version": VERSION, "phase": "pilot", "status": status,
            "eligible_for_main_analysis": False, "main_dispatch_allowed": False,
            "slot_id": self.slot["slot_id"], "plan_sha256": self.plan_sha256,
            "observed_model": self.model, "observed_inference_config": self.config,
            "model_dispatch_attempts": self.dispatch_attempts,
            "source_file_sha256s": self.source_hashes,
            "source_post_sha256s": source_post,
            "source_unchanged": source_post == self.source_hashes,
            "request_response_archive": self.calls, "actions": self.actions,
            "decision_count": len(self.actions),
            "submission_count": sum(row["submission"] for row in self.actions),
            "remaining_decisions": DECISION_CAP - len(self.actions),
            "stop_reason": stop,
            "early_voluntary_stop": stop == "VOLUNTARY" and len(self.actions) < DECISION_CAP,
            "budget_edge_voluntary_stop": stop == "VOLUNTARY" and len(self.actions) == DECISION_CAP,
            "invalidated_reason": reason, "replacement_count": 0,
            "feedback_independently_verified": False,
            "semantic_oracle_verification": False,
            "transport_failure": self.failure,
            "orphaned_raw_files": orphaned_raw,
        }
        _record(self.output_dir, "slot_receipt.json", receipt)
        self.closed = True
        return json.loads(_canonical(receipt))


def verify_excluded_live_trace(output_dir: Path) -> dict[str, Any]:
    """Rehash an excluded completed/invalidated trace, never admit it as main."""
    root = Path(output_dir)
    opened = _json_object((root / "slot_open.json").read_bytes(), "slot open")
    receipt = _json_object((root / "slot_receipt.json").read_bytes(), "slot receipt")
    inventory = _json_object((root / "source_inventory.json").read_bytes(),
                             "source inventory")
    if (opened.get("phase") != "pilot" or receipt.get("phase") != "pilot"
            or opened.get("status") != "EXCLUDED_LIVE_DISPATCH_OPEN"
            or opened.get("eligible_for_main_analysis") is not False
            or opened.get("main_dispatch_allowed") is not False
            or opened.get("replacement_count") != 0
            or receipt.get("eligible_for_main_analysis") is not False
            or receipt.get("main_dispatch_allowed") is not False
            or receipt.get("replacement_count") != 0
            or opened.get("slot_id") != receipt.get("slot_id")
            or opened.get("plan_sha256") != receipt.get("plan_sha256")
            or opened.get("observed_model") != receipt.get("observed_model")
            or opened.get("observed_inference_config") != receipt.get("observed_inference_config")
            or inventory.get("source_file_sha256s") != receipt.get("source_file_sha256s")):
        raise LiveDispatchError("excluded trace identity differs")
    plan_raw = (root / "plan_snapshot.json").read_bytes()
    if _sha(plan_raw) != receipt["plan_sha256"]:
        raise LiveDispatchError("plan snapshot differs")
    plan = _json_object(plan_raw, "plan snapshot")
    if (plan.get("phase") != "main" or plan.get("status") != "PROPOSED_MAIN_UNGATED"
            or plan.get("eligible_for_main_analysis") is not False
            or plan.get("main_execution_implemented") is not False
            or plan.get("source_file_sha256s") != receipt.get("source_file_sha256s")
            or plan.get("inference_config") != receipt.get("observed_inference_config")
            or plan.get("models") != [receipt.get("observed_model")]):
        raise LiveDispatchError("plan snapshot is not the excluded proposed plan")
    source_hashes = receipt["source_file_sha256s"]
    for name, digest in source_hashes.items():
        if _sha(_relative_source((root / "source_archive").resolve(), name).read_bytes()) != digest:
            raise LiveDispatchError("archived source bytes differ")
    calls, actions = receipt.get("request_response_archive"), receipt.get("actions")
    if not isinstance(calls, list) or not isinstance(actions, list):
        raise LiveDispatchError("call or action ledger is missing")
    invalidated = receipt.get("status") == "INVALIDATED_EXCLUDED_LIVE"
    if (receipt.get("status") not in {
        "COMPLETED_EXCLUDED_UNVERIFIED", "INVALIDATED_EXCLUDED_LIVE"
    } or invalidated is not (receipt.get("invalidated_reason") is not None)
            or len(calls) > DECISION_CAP or len(actions) > len(calls)
            or len(calls) > len(actions) + int(invalidated)
            or receipt.get("model_dispatch_attempts") != len(calls)):
        raise LiveDispatchError("slot completion or call accounting differs")
    referenced_raw = {
        value for call in calls for value in
        (call.get("request_path"), call.get("response_path")) if isinstance(value, str)
    }
    orphaned_raw = [
        {"path": path.name, "sha256": _sha(path.read_bytes()),
         "length": path.stat().st_size}
        for pattern in ("request-*.bin", "response-*.bin")
        for path in sorted(root.glob(pattern))
        if path.name not in referenced_raw
    ]
    if (orphaned_raw != receipt.get("orphaned_raw_files")
            or (not invalidated and orphaned_raw)):
        raise LiveDispatchError("unlinked raw archive inventory differs")
    for sequence, call in enumerate(calls, 1):
        if (call.get("sequence") != sequence
                or call.get("request_path") != f"request-{sequence:06d}.bin"
                or call.get("start_path") != f"dispatch-start-{sequence:06d}.json"
                or call.get("endpoint") != "/api/chat"):
            raise LiveDispatchError("call identity differs")
        request = (root / call["request_path"]).read_bytes()
        start = _json_object((root / call["start_path"]).read_bytes(), "dispatch start")
        if (_sha(request) != call.get("request_sha256")
                or len(request) != call.get("request_length")
                or start.get("schema_version") != VERSION
                or start.get("phase") != "pilot"
                or start.get("eligible_for_main_analysis") is not False
                or start.get("slot_id") != opened["slot_id"]
                or start.get("sequence") != sequence
                or start.get("endpoint") != "/api/chat"
                or start.get("request_path") != call["request_path"]
                or start.get("request_sha256") != call["request_sha256"]
                or start.get("request_length") != len(request)
                or start.get("observed_model") != receipt["observed_model"]
                or start.get("inference_config_sha256") != _sha(_canonical(
                    receipt["observed_inference_config"]))):
            raise LiveDispatchError("pre-dispatch archive differs")
        _strict_json(request, "archived request")
        request_json = _json_object(request, "archived request")
        config = receipt["observed_inference_config"]
        if (request_json.get("model") != receipt["observed_model"]["name"]
                or request_json.get("stream") is not False
                or request_json.get("think") is not False
                or _canonical(request_json.get("options")) != _canonical({
                    "temperature": config["temperature"], "num_ctx": config["num_ctx"],
                    "num_predict": config["max_output_tokens"],
                    "seed": opened["episode_seed"],
                })):
            raise LiveDispatchError("archived request model/options differ")
        if call.get("response_path") is None:
            if not invalidated or sequence != len(calls):
                raise LiveDispatchError("non-final call has no response")
            continue
        if call.get("response_path") != f"response-{sequence:06d}.bin":
            raise LiveDispatchError("response archive path differs")
        response = (root / call["response_path"]).read_bytes()
        if (_sha(response) != call.get("response_sha256")
                or len(response) != call.get("response_length")):
            raise LiveDispatchError("post-dispatch archive differs")
        if call.get("return_path") is None:
            if (not invalidated or sequence != len(calls)
                    or receipt.get("invalidated_reason") != "RESPONSE_ARCHIVE_FAILURE"):
                raise LiveDispatchError("completed response lacks return receipt")
        else:
            if call["return_path"] != f"dispatch-return-{sequence:06d}.json":
                raise LiveDispatchError("dispatch return path differs")
            returned = _json_object((root / call["return_path"]).read_bytes(),
                                    "dispatch return")
            if (returned.get("schema_version") != VERSION
                    or returned.get("phase") != "pilot"
                    or returned.get("eligible_for_main_analysis") is not False
                    or returned.get("slot_id") != opened["slot_id"]
                    or returned.get("sequence") != sequence
                    or returned.get("response_path") != call["response_path"]
                    or returned.get("response_sha256") != call["response_sha256"]
                    or returned.get("response_length") != len(response)):
                raise LiveDispatchError("post-dispatch return receipt differs")
    if (receipt.get("decision_count") != len(actions)
            or receipt.get("submission_count") != sum(row.get("submission") is True
                                                       for row in actions)
            or receipt.get("remaining_decisions") != DECISION_CAP - len(actions)):
        raise LiveDispatchError("decision accounting differs")
    for sequence, action in enumerate(actions, 1):
        if (action.get("decision") != sequence
                or action.get("request_sequence") != sequence):
            raise LiveDispatchError("action sequence differs")
        saved = _json_object((root / f"decision-{sequence:06d}.json").read_bytes(),
                             "decision")
        response = (root / calls[sequence - 1]["response_path"]).read_bytes()
        _check_response_envelope(response, "archived response")
        name, payload = _response_action(response)
        _canonical(payload)
        if (saved != action or action.get("action") != name.upper()
                or action.get("submission") is not (name == "attempt")
                or action.get("candidate_sha256") != (
                    _sha(_canonical(payload["candidate"])) if name == "attempt" else None)
                or action.get("feedback_independently_verified") is not False
                or (action.get("scripted_public_verdict") in {"PASS", "FAIL"})
                   is not (name == "attempt")):
            raise LiveDispatchError("action differs from response or feedback status")
    stop = receipt.get("stop_reason")
    last_action = actions[-1].get("action") if actions else None
    if (not invalidated and (
        (stop == "BUDGET" and (len(actions) != DECISION_CAP
                                or last_action in {"TERMINATE", "CLAIM"}))
        or (stop == "VOLUNTARY" and last_action not in {"TERMINATE", "CLAIM"})
        or (stop == "TIMEOUT" and (len(actions) >= DECISION_CAP or not calls))
        or stop not in {"BUDGET", "VOLUNTARY", "TIMEOUT"}
        or receipt.get("source_unchanged") is not True
    )) or (invalidated and stop != "INFRASTRUCTURE_ABORT"):
        raise LiveDispatchError("stop reason contradicts decisions")
    if (receipt.get("early_voluntary_stop") is not (stop == "VOLUNTARY"
                                                    and len(actions) < DECISION_CAP)
            or receipt.get("budget_edge_voluntary_stop") is not (
                stop == "VOLUNTARY" and len(actions) == DECISION_CAP)
            or receipt.get("source_unchanged") is not (
                receipt.get("source_post_sha256s") == source_hashes)
            or receipt.get("feedback_independently_verified") is not False
            or receipt.get("semantic_oracle_verification") is not False):
        raise LiveDispatchError("excluded stop or verification flags differ")
    return receipt
