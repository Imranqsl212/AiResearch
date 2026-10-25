"""Measurement-only Bandit sidecar for exact Python source bytes.

This excluded scanner does not execute candidate code, provide agent feedback,
change a benchmark gate, or establish that code is secure. It is inapplicable to
the symbolic JSON candidates in the finite-policy experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


VERSION = "excluded-independent-bandit-v0.1.0"
REQUIRED_BANDIT_VERSION = "bandit 1.9.4"
MAX_SOURCE_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 60
SCAN_ARGS = ("--ignore-nosec", "-f", "json", "-")
RAW_FILES = ("source.py", "bandit.raw.json", "bandit.stderr.bin",
             "bandit.version.stdout.bin", "bandit.version.stderr.bin")
REQUIRED_FLAGS = {"phase": "excluded", "eligible_for_main_analysis": False,
                  "measurement_only": True, "agent_visible": False,
                  "changes_benchmark_gate": False}
LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "UNDEFINED"})


class SASTReceiptError(ValueError):
    """A sidecar input or saved receipt violates its contract."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _write_once(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _read_source(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SASTReceiptError("source must be an ordinary file")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise SASTReceiptError("source exceeds the 64 KiB limit")
    raw = path.read_bytes()
    if len(raw) > MAX_SOURCE_BYTES:
        raise SASTReceiptError("source changed beyond the 64 KiB limit")
    return raw


def _resolve_bandit(requested: str) -> Path | None:
    found = shutil.which(requested)
    if found is None:
        return None
    path = Path(found).resolve(strict=True)
    return path if path.is_file() and os.access(path, os.X_OK) else None


def _run(argv: list[str], *, stdin: bytes, timeout: int, cwd: Path) -> dict[str, Any]:
    # Never invoke a shell or import/execute the candidate source.
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    try:
        process = subprocess.run(argv, input=stdin, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, cwd=cwd, env=env,
                                 timeout=timeout, shell=False, check=False)
        code, timed_out, launch_error = process.returncode, False, None
        stdout, stderr = process.stdout, process.stderr
    except subprocess.TimeoutExpired as exc:
        code, timed_out, launch_error = None, True, None
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
    except OSError as exc:
        code, timed_out, launch_error = None, False, type(exc).__name__
        stdout, stderr = b"", b""
    return {"returncode": code, "timed_out": timed_out,
            "launch_error": launch_error,
            "stdout_truncated": len(stdout) > MAX_OUTPUT_BYTES,
            "stderr_truncated": len(stderr) > MAX_OUTPUT_BYTES,
            "stdout": stdout[:MAX_OUTPUT_BYTES],
            "stderr": stderr[:MAX_OUTPUT_BYTES]}


def _empty_process() -> dict[str, Any]:
    return {"returncode": None, "timed_out": False, "launch_error": None,
            "stdout_truncated": False, "stderr_truncated": False,
            "stdout": b"", "stderr": b""}


def _is_unrun_process(process: dict[str, Any], stdout: bytes, stderr: bytes) -> bool:
    return (_process_fields(process) == _process_fields(_empty_process()) and
            not stdout and not stderr)


def _process_fields(process: dict[str, Any]) -> dict[str, Any]:
    return {key: process[key] for key in ("returncode", "timed_out", "launch_error",
                                         "stdout_truncated", "stderr_truncated")}


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _normalize(raw: bytes) -> tuple[str, list[dict[str, Any]]]:
    report = json.loads(raw, object_pairs_hook=_unique_pairs)
    if (not isinstance(report, dict) or
            not isinstance(report.get("errors"), list) or
            not isinstance(report.get("results"), list)):
        raise ValueError("Bandit JSON lacks errors/results arrays")
    if report["errors"]:
        errors = report["errors"]
        if all(isinstance(row, dict) and isinstance(row.get("reason"), str)
               for row in errors) and any("syntax error" in row["reason"].lower()
                                       for row in errors):
            return "SOURCE_SYNTAX_ERROR", []
        return "ENGINE_REPORTED_ERRORS", []
    findings: list[dict[str, Any]] = []
    for row in report["results"]:
        if not isinstance(row, dict):
            raise ValueError("Bandit finding is not an object")
        test_id, test_name = row.get("test_id"), row.get("test_name")
        severity, confidence = row.get("issue_severity"), row.get("issue_confidence")
        line, message = row.get("line_number"), row.get("issue_text")
        cwe = row.get("issue_cwe")
        if (not isinstance(test_id, str) or re.fullmatch(r"B[0-9]+", test_id) is None
                or not isinstance(test_name, str) or not test_name
                or severity not in LEVELS or confidence not in LEVELS
                or type(line) is not int or line < 1
                or not isinstance(message, str) or not message
                or row.get("filename") != "<stdin>"
                or (cwe is not None and (not isinstance(cwe, dict)
                                         or type(cwe.get("id")) is not int
                                         or cwe["id"] < 1))):
            raise ValueError("Bandit finding has invalid fields")
        findings.append({"test_id": test_id, "test_name": test_name,
                         "severity": severity, "confidence": confidence,
                         "line": line, "message": message,
                         "cwe_id": cwe["id"] if cwe else None})
    findings.sort(key=lambda item: (item["line"], item["test_id"],
                                    item["message"], item["severity"],
                                    item["confidence"], item["test_name"]))
    return "COMPLETE", findings


def _version_text(process: dict[str, Any], raw: bytes) -> str | None:
    if process["returncode"] != 0 or process["timed_out"] or process["launch_error"]:
        return None
    try:
        value = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    return value or None


def _classify(engine: dict[str, Any], version: dict[str, Any],
              scan: dict[str, Any], raw: bytes) -> tuple[str, str | None, list[dict[str, Any]]]:
    if engine["resolved_path"] is None:
        return "INDETERMINATE", "ENGINE_MISSING", []
    if version["timed_out"]:
        return "INDETERMINATE", "VERSION_TIMEOUT", []
    if version["launch_error"]:
        return "INDETERMINATE", "VERSION_LAUNCH_ERROR", []
    if version["stdout_truncated"] or version["stderr_truncated"]:
        return "INDETERMINATE", "VERSION_OUTPUT_TOO_LARGE", []
    if engine["version"] is None:
        return "INDETERMINATE", "VERSION_INVALID", []
    if engine["version"].splitlines()[0].strip() != REQUIRED_BANDIT_VERSION:
        return "INDETERMINATE", "VERSION_MISMATCH", []
    if scan["timed_out"]:
        return "INDETERMINATE", "SCAN_TIMEOUT", []
    if scan["launch_error"]:
        return "INDETERMINATE", "SCAN_LAUNCH_ERROR", []
    if scan["stdout_truncated"] or scan["stderr_truncated"]:
        return "INDETERMINATE", "SCAN_OUTPUT_TOO_LARGE", []
    if scan["returncode"] not in {0, 1}:
        return "INDETERMINATE", "SCAN_EXIT_CODE", []
    try:
        reason, findings = _normalize(raw)
    except (ValueError, UnicodeDecodeError, TypeError):
        return "INDETERMINATE", "SCAN_REPORT_INVALID", []
    if reason != "COMPLETE":
        return "INDETERMINATE", reason, []
    if (scan["returncode"] == 0 and findings) or (scan["returncode"] == 1 and not findings):
        return "INDETERMINATE", "SCAN_EXIT_RESULT_MISMATCH", []
    return ("FINDINGS" if findings else "NO_FINDINGS"), None, findings


def scan_source(*, source_path: Path, output_dir: Path,
                bandit: str = "bandit", timeout_seconds: int = 20) -> dict[str, Any]:
    """Run Bandit on stdin and archive a separate, write-once sidecar."""
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise SASTReceiptError("timeout must be an integer in 1..60 seconds")
    source = _read_source(Path(source_path))
    output_dir = Path(output_dir)
    output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(output_dir, 0o700)
    _write_once(output_dir / "source.py", source)
    executable = _resolve_bandit(bandit)
    engine = {"requested": bandit,
              "resolved_path": str(executable) if executable else None,
              "executable_sha256": _sha(executable.read_bytes()) if executable else None,
              "version": None}
    version = (_run([str(executable), "--version"], stdin=b"",
                    timeout=timeout_seconds, cwd=output_dir)
               if executable else _empty_process())
    if executable:
        engine["version"] = _version_text(version, version["stdout"])
    scan = (_run([str(executable), *SCAN_ARGS], stdin=source,
                 timeout=timeout_seconds, cwd=output_dir)
            if engine["version"] is not None and
            engine["version"].splitlines()[0].strip() == REQUIRED_BANDIT_VERSION and not (
                version["stdout_truncated"] or version["stderr_truncated"])
            else _empty_process())
    if executable and _sha(executable.read_bytes()) != engine["executable_sha256"]:
        raise SASTReceiptError("Bandit executable changed during the scan")
    for name, raw in (("bandit.raw.json", scan["stdout"]),
                      ("bandit.stderr.bin", scan["stderr"]),
                      ("bandit.version.stdout.bin", version["stdout"]),
                      ("bandit.version.stderr.bin", version["stderr"])):
        _write_once(output_dir / name, raw)
    status, reason, findings = _classify(engine, version, scan, scan["stdout"])
    receipt = {
        "schema_version": VERSION, **REQUIRED_FLAGS,
        "source_sha256": _sha(source), "source_size_bytes": len(source),
        "engine": engine, "version_process": _process_fields(version),
        "scan_process": _process_fields(scan),
        "scan_argv": [str(executable), *SCAN_ARGS] if executable else None,
        "timeout_seconds": timeout_seconds,
        "artifact_sha256s": {name: _sha((output_dir / name).read_bytes())
                             for name in RAW_FILES},
        "status": status, "reason": reason,
        "normalized_findings": findings,
    }
    _write_once(output_dir / "receipt.json", _canonical(receipt) + b"\n")
    return receipt


def verify_receipt(*, source_path: Path, archive_dir: Path,
                   bandit_executable: Path | None = None) -> dict[str, Any]:
    """Recompute hashes, findings and status from the archived raw artifacts.

    The optional executable check binds a currently available Bandit binary.
    This verifies report consistency, not the truth of its alerts.
    """
    root = Path(archive_dir)
    if (not root.is_dir() or
            {item.name for item in root.iterdir()} != set(RAW_FILES) | {"receipt.json"} or
            any(item.is_symlink() or not item.is_file() for item in root.iterdir())):
        raise SASTReceiptError("sidecar archive inventory differs")
    try:
        receipt = json.loads((root / "receipt.json").read_bytes(),
                             object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, ValueError) as exc:
        raise SASTReceiptError("receipt is not valid unique-key JSON") from exc
    if not isinstance(receipt, dict):
        raise SASTReceiptError("receipt must be an object")
    raw = {name: (root / name).read_bytes() for name in RAW_FILES}
    if (any(receipt.get(key) != value for key, value in REQUIRED_FLAGS.items()) or
            receipt.get("schema_version") != VERSION or
            receipt.get("artifact_sha256s") != {name: _sha(value)
                                                 for name, value in raw.items()} or
            receipt.get("source_sha256") != _sha(raw["source.py"]) or
            receipt.get("source_size_bytes") != len(raw["source.py"]) or
            len(raw["source.py"]) > MAX_SOURCE_BYTES or
            any(len(raw[name]) > MAX_OUTPUT_BYTES for name in RAW_FILES[1:]) or
            _read_source(Path(source_path)) != raw["source.py"]):
        raise SASTReceiptError("source or raw artifact hash differs")
    engine = receipt.get("engine")
    version = receipt.get("version_process")
    scan = receipt.get("scan_process")
    if not isinstance(engine, dict) or not isinstance(version, dict) or not isinstance(scan, dict):
        raise SASTReceiptError("engine or process metadata missing")
    process_keys = {"returncode", "timed_out", "launch_error",
                    "stdout_truncated", "stderr_truncated"}
    if (set(engine) != {"requested", "resolved_path", "executable_sha256", "version"} or
            not isinstance(engine["requested"], str) or
            set(version) != process_keys or set(scan) != process_keys or
            any(type(meta["timed_out"]) is not bool or
                type(meta["stdout_truncated"]) is not bool or
                type(meta["stderr_truncated"]) is not bool or
                (meta["returncode"] is not None and type(meta["returncode"]) is not int) or
                (meta["launch_error"] is not None and not isinstance(meta["launch_error"], str))
                for meta in (version, scan)) or
            type(receipt.get("timeout_seconds")) is not int or
            not 1 <= receipt["timeout_seconds"] <= MAX_TIMEOUT_SECONDS):
        raise SASTReceiptError("scanner metadata malformed")
    if ((version["stdout_truncated"] and
         len(raw["bandit.version.stdout.bin"]) != MAX_OUTPUT_BYTES) or
            (version["stderr_truncated"] and
             len(raw["bandit.version.stderr.bin"]) != MAX_OUTPUT_BYTES) or
            (scan["stdout_truncated"] and len(raw["bandit.raw.json"]) != MAX_OUTPUT_BYTES) or
            (scan["stderr_truncated"] and
             len(raw["bandit.stderr.bin"]) != MAX_OUTPUT_BYTES)):
        raise SASTReceiptError("truncated process output has inconsistent length")
    resolved = engine["resolved_path"]
    if resolved is None:
        if (engine["executable_sha256"] is not None or engine["version"] is not None or
                receipt.get("scan_argv") is not None or
                any(raw[name] for name in RAW_FILES[1:]) or
                not _is_unrun_process(version, raw["bandit.version.stdout.bin"],
                                      raw["bandit.version.stderr.bin"]) or
                not _is_unrun_process(scan, raw["bandit.raw.json"],
                                      raw["bandit.stderr.bin"])):
            raise SASTReceiptError("missing engine has scan artifacts")
    elif (not isinstance(resolved, str) or not Path(resolved).is_absolute() or
          not isinstance(engine["executable_sha256"], str) or
          re.fullmatch(r"[0-9a-f]{64}", engine["executable_sha256"]) is None or
          receipt.get("scan_argv") != [resolved, *SCAN_ARGS]):
        raise SASTReceiptError("Bandit executable identity or command differs")
    if bandit_executable is not None:
        trusted = Path(bandit_executable).resolve(strict=True)
        if str(trusted) != resolved or _sha(trusted.read_bytes()) != engine["executable_sha256"]:
            raise SASTReceiptError("trusted Bandit executable differs")
    if engine["version"] != _version_text(version, raw["bandit.version.stdout.bin"]):
        raise SASTReceiptError("Bandit version does not match raw output")
    should_have_scanned = (engine["version"] is not None and
                           engine["version"].splitlines()[0].strip() ==
                           REQUIRED_BANDIT_VERSION and
                           not version["stdout_truncated"] and
                           not version["stderr_truncated"])
    if not should_have_scanned and not _is_unrun_process(
            scan, raw["bandit.raw.json"], raw["bandit.stderr.bin"]):
        raise SASTReceiptError("scan artifacts exist despite failed version check")
    if should_have_scanned and _is_unrun_process(
            scan, raw["bandit.raw.json"], raw["bandit.stderr.bin"]):
        raise SASTReceiptError("scan process was not recorded")
    status, reason, findings = _classify(engine, version, scan, raw["bandit.raw.json"])
    if (receipt.get("status"), receipt.get("reason"),
            receipt.get("normalized_findings")) != (status, reason, findings):
        raise SASTReceiptError("saved SAST result differs from raw Bandit output")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="scan one Python source into a fresh archive")
    scan.add_argument("--source", type=Path, required=True)
    scan.add_argument("--output-dir", type=Path, required=True)
    scan.add_argument("--bandit", default="bandit")
    scan.add_argument("--timeout-seconds", type=int, default=20)
    verify = sub.add_parser("verify", help="verify an existing SAST archive")
    verify.add_argument("--source", type=Path, required=True)
    verify.add_argument("--archive-dir", type=Path, required=True)
    verify.add_argument("--bandit", type=Path)
    args = parser.parse_args()
    if args.command == "scan":
        receipt = scan_source(source_path=args.source, output_dir=args.output_dir,
                              bandit=args.bandit, timeout_seconds=args.timeout_seconds)
        verify_receipt(source_path=args.source, archive_dir=args.output_dir)
    else:
        receipt = verify_receipt(source_path=args.source, archive_dir=args.archive_dir,
                                 bandit_executable=args.bandit)
    print(json.dumps({"status": receipt["status"], "reason": receipt["reason"],
                      "finding_count": len(receipt["normalized_findings"])}, sort_keys=True))
    return 2 if receipt["status"] == "INDETERMINATE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
