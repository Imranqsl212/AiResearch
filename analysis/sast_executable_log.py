"""Post-collection SAST sidecars for executable Python attempt logs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from analysis.independent_sast import (
    MAX_SOURCE_BYTES, MAX_TIMEOUT_SECONDS, VERSION as SAST_VERSION,
    scan_source, verify_receipt,
)

VERSION = "excluded-executable-log-sast-v0.1.0"
NATIVE_LOG_SCHEMA_VERSION = "0.1.0"
MAX_LOG_BYTES = 32 * 1024 * 1024
MAX_RUN_RECEIPT_BYTES = 2 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
COMPLETE = frozenset({"FINDINGS", "NO_FINDINGS"})
FLAGS = {"phase": "excluded_post_collection", "measurement_only": True,
         "agent_visible": False, "changes_benchmark_gate": False,
         "eligible_for_main_analysis": False}


class ExecutableLogSASTError(ValueError):
    """A saved log or SAST archive violates its integrity contract."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExecutableLogSASTError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ExecutableLogSASTError("non-finite JSON constant")


def _write_once(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _attempts(log_path: Path) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    if log_path.is_symlink() or not log_path.is_file():
        raise ExecutableLogSASTError("log must be an ordinary file")
    if log_path.stat().st_size > MAX_LOG_BYTES:
        raise ExecutableLogSASTError("log exceeds size limit")
    raw = log_path.read_bytes()
    if len(raw) > MAX_LOG_BYTES or not raw:
        raise ExecutableLogSASTError("log is empty or changed beyond size limit")
    attempts: list[dict[str, Any]] = []
    seen: set[str] = set()
    final_event: dict[str, Any] | None = None
    last_event: dict[str, Any] | None = None
    for line_number, line in enumerate(raw.splitlines(), 1):
        try:
            event = json.loads(line, object_pairs_hook=_unique_pairs,
                               parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ExecutableLogSASTError(f"invalid JSONL at line {line_number}") from exc
        if not isinstance(event, dict):
            raise ExecutableLogSASTError("log event is not an object")
        last_event = event
        if event.get("event_type") == "RUN_FINISHED":
            if final_event is not None:
                raise ExecutableLogSASTError("log has multiple RUN_FINISHED events")
            final_event = event
        if event.get("event_type") != "TOOL_OBSERVATION" or event.get("tool") != "attempt":
            continue
        event_id, step = event.get("event_id"), event.get("step")
        if (not isinstance(event_id, str) or not re.fullmatch(r"event-[0-9]{5}", event_id)
                or event_id in seen or type(step) is not int or step < 1):
            raise ExecutableLogSASTError("attempt event identity or step is invalid")
        seen.add(event_id)
        attempts.append({"event": event, "event_id": event_id,
                         "step": step, "line_number": line_number})
    if not attempts:
        raise ExecutableLogSASTError("log has no executable attempt observations")
    if final_event is None or last_event is not final_event:
        raise ExecutableLogSASTError("log is not a finished episode")
    identity = ("schema_version", "experiment_id", "run_id", "public_run_id",
                "task_id", "public_task_id", "condition", "model",
                "agent_version", "benchmark_version", "git_commit")
    if (final_event.get("schema_version") != NATIVE_LOG_SCHEMA_VERSION
            or any(not isinstance(final_event.get(key), str) or not final_event[key]
                   for key in identity)
            or not isinstance(final_event.get("event_id"), str)
            or re.fullmatch(r"event-[0-9]{5}", final_event["event_id"]) is None
            or type(final_event.get("step")) is not int
            or final_event["step"] < 0
            or not isinstance(final_event.get("outcome"), str)
            or not final_event["outcome"]
            or not isinstance(final_event.get("stop_event"), str)
            or not final_event["stop_event"]):
        raise ExecutableLogSASTError("RUN_FINISHED event is malformed")
    receipt_path = log_path.with_suffix(".receipt.json")
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ExecutableLogSASTError("sibling finalized-run receipt is missing")
    if receipt_path.stat().st_size > MAX_RUN_RECEIPT_BYTES:
        raise ExecutableLogSASTError("sibling finalized-run receipt exceeds size limit")
    receipt_raw = receipt_path.read_bytes()
    if len(receipt_raw) > MAX_RUN_RECEIPT_BYTES:
        raise ExecutableLogSASTError("sibling finalized-run receipt changed beyond size limit")
    try:
        receipt = json.loads(receipt_raw, object_pairs_hook=_unique_pairs,
                             parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ExecutableLogSASTError("sibling finalized-run receipt is invalid JSON") from exc
    if not isinstance(receipt, dict):
        raise ExecutableLogSASTError("sibling finalized-run receipt is not an object")
    if (receipt.get("log_file") != log_path.name
            or receipt.get("log_sha256") != _sha(raw)
            or any(receipt.get(key) != final_event.get(key) for key in identity)
            or receipt.get("terminal_outcome") != final_event.get("outcome")
            or receipt.get("stop_event") != final_event.get("stop_event")
            or not isinstance(receipt.get("run_id"), str)
            or not receipt["run_id"]):
        raise ExecutableLogSASTError("sibling receipt does not bind finished log")
    for item in attempts:
        if any(item["event"].get(key) != final_event.get(key) for key in identity):
            raise ExecutableLogSASTError("attempt belongs to a different run")
    native = {"run_receipt_name": receipt_path.name,
              "run_receipt_sha256": _sha(receipt_raw),
              "finished_event_id": final_event.get("event_id"),
              "run_id": receipt["run_id"]}
    return raw, attempts, native


def _source_state(event: dict[str, Any]) -> tuple[dict[str, Any], bytes | None]:
    parameters = event.get("parameters")
    source = parameters.get("source") if isinstance(parameters, dict) else None
    verifier = event.get("verifier_result")
    verifier_hash = (verifier.get("source_sha256")
                     if isinstance(verifier, dict) else None)
    if not isinstance(source, str) or not source:
        return ({"source_sha256": None, "source_size_bytes": None,
                 "verifier_source_sha256": verifier_hash,
                 "sast_status": "UNSCANNABLE_SOURCE_MISSING",
                 "reason": "SOURCE_NOT_AVAILABLE"}, None)
    try:
        source_bytes = source.encode("utf-8")
    except UnicodeEncodeError:
        return ({"source_sha256": None, "source_size_bytes": None,
                 "verifier_source_sha256": verifier_hash,
                 "sast_status": "UNSCANNABLE_SOURCE_MISSING",
                 "reason": "SOURCE_NOT_UTF8"}, None)
    digest = _sha(source_bytes)
    base = {"source_sha256": digest, "source_size_bytes": len(source_bytes),
            "verifier_source_sha256": verifier_hash}
    for field in ("action", "raw_action"):
        action = event.get(field)
        if isinstance(action, dict):
            nested = action.get("parameters")
            if isinstance(nested, dict) and "source" in nested and nested["source"] != source:
                return ({**base, "sast_status": "UNSCANNABLE_SOURCE_MISMATCH",
                         "reason": "ACTION_SOURCE_DISAGREES"}, None)
    if (not isinstance(verifier_hash, str) or HEX64.fullmatch(verifier_hash) is None
            or digest != verifier_hash):
        return ({**base, "sast_status": "UNSCANNABLE_SOURCE_MISMATCH",
                 "reason": "VERIFIER_SOURCE_HASH_DISAGREES"}, None)
    return base, source_bytes


def _engine_identity(receipt: dict[str, Any]) -> dict[str, Any]:
    """Record the exact scanner identity shared by every scanned attempt."""
    engine = receipt["engine"]
    return {"resolved_path": engine["resolved_path"],
            "executable_sha256": engine["executable_sha256"],
            "version": engine["version"],
            "scan_argv": receipt["scan_argv"]}


def scan_executable_log(*, log_path: Path, output_dir: Path,
                        bandit: str = "bandit", timeout_seconds: int = 20
                        ) -> dict[str, Any]:
    """Create write-once SAST sidecars for hash-matched attempts only."""
    if (type(timeout_seconds) is not int
            or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS):
        raise ExecutableLogSASTError("timeout must be an integer in 1..60 seconds")
    if not isinstance(bandit, str) or not bandit:
        raise ExecutableLogSASTError("Bandit executable must be a nonempty string")
    log_path, output_dir = Path(log_path), Path(output_dir)
    raw, attempts, native = _attempts(log_path)
    output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(output_dir, 0o700)
    rows: list[dict[str, Any]] = []
    engine_identity: dict[str, Any] | None = None
    for ordinal, item in enumerate(attempts, 1):
        state, source = _source_state(item["event"])
        row = {"ordinal": ordinal, "event_id": item["event_id"],
               "step": item["step"], "log_line_number": item["line_number"],
               **state, "sidecar_dir": None, "sidecar_receipt_sha256": None}
        if source is not None and len(source) > MAX_SOURCE_BYTES:
            row.update(sast_status="INDETERMINATE", reason="SOURCE_EXCEEDS_SAST_LIMIT")
        elif source is not None:
            sidecar_name = f"attempt-{ordinal:06d}"
            with tempfile.TemporaryDirectory(prefix="sast-executable-source-") as temporary:
                source_path = Path(temporary) / "source.py"
                source_path.write_bytes(source)
                receipt = scan_source(source_path=source_path,
                                      output_dir=output_dir / sidecar_name,
                                      bandit=bandit,
                                      timeout_seconds=timeout_seconds)
                verify_receipt(source_path=source_path,
                               archive_dir=output_dir / sidecar_name)
            current_identity = _engine_identity(receipt)
            if engine_identity is None:
                engine_identity = current_identity
            elif engine_identity != current_identity:
                raise ExecutableLogSASTError("Bandit identity changed across attempts")
            row.update(sast_status=receipt["status"], reason=receipt["reason"],
                       sidecar_dir=sidecar_name,
                       sidecar_receipt_sha256=_sha(
                           (output_dir / sidecar_name / "receipt.json").read_bytes()))
        rows.append(row)
    manifest = {"schema_version": VERSION, **FLAGS,
                "sast_adapter_version": SAST_VERSION,
                "log_name": log_path.name, "log_sha256": _sha(raw),
                "log_size_bytes": len(raw), **native,
                "engine_requested": bandit, "engine_identity": engine_identity,
                "timeout_seconds": timeout_seconds, "attempt_count": len(rows),
                "attempts": rows}
    _write_once(output_dir / "manifest.json", _canonical(manifest) + b"\n")
    verify_executable_log(log_path=log_path, archive_dir=output_dir)
    return manifest


def verify_executable_log(*, log_path: Path, archive_dir: Path,
                          bandit_executable: Path | None = None) -> dict[str, Any]:
    """Replay log/source bindings and saved SAST receipts without re-scanning."""
    raw, attempts, native = _attempts(Path(log_path))
    archive_dir = Path(archive_dir)
    if archive_dir.is_symlink() or not archive_dir.is_dir():
        raise ExecutableLogSASTError("SAST archive must be an ordinary directory")
    manifest_path = archive_dir / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ExecutableLogSASTError("SAST manifest missing or symlinked")
    try:
        manifest = json.loads(manifest_path.read_bytes(),
                              object_pairs_hook=_unique_pairs,
                              parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ExecutableLogSASTError("SAST manifest is invalid JSON") from exc
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != VERSION
            or any(manifest.get(key) != value for key, value in FLAGS.items())
            or manifest.get("sast_adapter_version") != SAST_VERSION
            or manifest.get("log_name") != Path(log_path).name
            or manifest.get("log_sha256") != _sha(raw)
            or manifest.get("log_size_bytes") != len(raw)
            or any(manifest.get(key) != value for key, value in native.items())
            or type(manifest.get("attempt_count")) is not int
            or manifest["attempt_count"] != len(attempts)
            or not isinstance(manifest.get("attempts"), list)
            or len(manifest["attempts"]) != len(attempts)
            or not isinstance(manifest.get("engine_requested"), str)
            or not manifest["engine_requested"]
            or (manifest.get("engine_identity") is not None
                and not isinstance(manifest["engine_identity"], dict))
            or type(manifest.get("timeout_seconds")) is not int
            or not 1 <= manifest["timeout_seconds"] <= MAX_TIMEOUT_SECONDS):
        raise ExecutableLogSASTError("SAST manifest/log binding differs")
    expected_children = {"manifest.json"}
    observed_identity: dict[str, Any] | None = None
    for ordinal, (item, row) in enumerate(zip(attempts, manifest["attempts"], strict=True), 1):
        if not isinstance(row, dict):
            raise ExecutableLogSASTError("SAST attempt row is not an object")
        state, source = _source_state(item["event"])
        common = {"ordinal": ordinal, "event_id": item["event_id"],
                  "step": item["step"], "log_line_number": item["line_number"],
                  "source_sha256": state["source_sha256"],
                  "source_size_bytes": state["source_size_bytes"],
                  "verifier_source_sha256": state["verifier_source_sha256"]}
        if any(row.get(key) != value for key, value in common.items()):
            raise ExecutableLogSASTError("SAST row no longer binds exact attempt source")
        if source is None:
            if (row.get("sast_status") != state["sast_status"]
                    or row.get("reason") != state["reason"]
                    or row.get("sidecar_dir") is not None
                    or row.get("sidecar_receipt_sha256") is not None):
                raise ExecutableLogSASTError("unscannable source was mislabeled")
            continue
        if len(source) > MAX_SOURCE_BYTES:
            if (row.get("sast_status") != "INDETERMINATE"
                    or row.get("reason") != "SOURCE_EXCEEDS_SAST_LIMIT"
                    or row.get("sidecar_dir") is not None
                    or row.get("sidecar_receipt_sha256") is not None):
                raise ExecutableLogSASTError("oversize source was mislabeled")
            continue
        sidecar_name = f"attempt-{ordinal:06d}"
        if (row.get("sidecar_dir") != sidecar_name
                or not isinstance(row.get("sidecar_receipt_sha256"), str)
                or HEX64.fullmatch(row["sidecar_receipt_sha256"]) is None):
            raise ExecutableLogSASTError("SAST sidecar identity differs")
        expected_children.add(sidecar_name)
        sidecar = archive_dir / sidecar_name
        if sidecar.is_symlink() or not sidecar.is_dir():
            raise ExecutableLogSASTError("SAST sidecar directory missing or symlinked")
        source_file = sidecar / "source.py"
        receipt_file = sidecar / "receipt.json"
        if (source_file.is_symlink() or not source_file.is_file()
                or receipt_file.is_symlink() or not receipt_file.is_file()):
            raise ExecutableLogSASTError("SAST sidecar source or receipt is not an ordinary file")
        if source_file.read_bytes() != source:
            raise ExecutableLogSASTError("SAST sidecar source differs from log")
        receipt_bytes = receipt_file.read_bytes()
        if _sha(receipt_bytes) != row["sidecar_receipt_sha256"]:
            raise ExecutableLogSASTError("SAST sidecar receipt hash differs")
        receipt = verify_receipt(source_path=source_file,
                                 archive_dir=sidecar,
                                 bandit_executable=bandit_executable)
        if (row.get("sast_status") != receipt["status"]
                or row.get("reason") != receipt["reason"]
                or receipt["source_sha256"] != state["source_sha256"]
                or receipt["engine"]["requested"] != manifest["engine_requested"]
                or receipt["timeout_seconds"] != manifest["timeout_seconds"]):
            raise ExecutableLogSASTError("SAST status differs from sidecar receipt")
        identity = _engine_identity(receipt)
        if observed_identity is None:
            observed_identity = identity
        elif observed_identity != identity:
            raise ExecutableLogSASTError("Bandit identity differs across sidecars")
    if manifest["engine_identity"] != observed_identity:
        raise ExecutableLogSASTError("manifest Bandit identity differs from sidecars")
    if ({item.name for item in archive_dir.iterdir()} != expected_children
            or any(item.is_symlink() for item in archive_dir.iterdir())):
        raise ExecutableLogSASTError("SAST archive inventory differs")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="scan one saved executable JSONL log")
    scan.add_argument("--log", type=Path, required=True)
    scan.add_argument("--output-dir", type=Path, required=True)
    scan.add_argument("--bandit", default="bandit")
    scan.add_argument("--timeout-seconds", type=int, default=20)
    verify = sub.add_parser("verify", help="verify a saved log and SAST archive")
    verify.add_argument("--log", type=Path, required=True)
    verify.add_argument("--archive-dir", type=Path, required=True)
    verify.add_argument("--bandit", type=Path)
    args = parser.parse_args()
    if args.command == "scan":
        result = scan_executable_log(log_path=args.log, output_dir=args.output_dir,
                                     bandit=args.bandit,
                                     timeout_seconds=args.timeout_seconds)
    else:
        result = verify_executable_log(log_path=args.log, archive_dir=args.archive_dir,
                                       bandit_executable=args.bandit)
    counts = {status: sum(row["sast_status"] == status for row in result["attempts"])
              for status in sorted({row["sast_status"] for row in result["attempts"]})}
    print(json.dumps({"attempt_count": result["attempt_count"], "statuses": counts,
                      "eligible_for_main_analysis": False}, sort_keys=True))
    return 2 if any(row["sast_status"] not in COMPLETE for row in result["attempts"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
