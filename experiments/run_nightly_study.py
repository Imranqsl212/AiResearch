"""Fail-closed overnight gate: preflight → Docker smoke → pilot → optional main.

The default stops after the pilot.  ``--run-main`` is an explicit opt-in because
the 80-task × 3-repeat series can exceed one night on an 8 GB laptop.  Every phase
is frozen and resumable; a failed safety/catalog gate prevents all agent execution.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from benchmark.executable_catalog import EXECUTABLE_BENCHMARK_VERSION
from experiments.run_executable_study import run_study


ROOT = Path(__file__).resolve().parents[1]
NIGHTLY_ROOT = ROOT / "experiments" / "nightly"


def _ollama_preflight(model: str) -> dict[str, Any]:
    request = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"passed": False, "model": model, "error": f"local Ollama preflight failed: {type(exc).__name__}: {str(exc)[:500]}"}
    available = [item.get("name") for item in payload.get("models", []) if isinstance(item, dict)]
    return {"passed": model in available, "model": model, "available_models": available, "error": None if model in available else f"model {model!r} is not installed locally"}


def _run_check(module: str, *arguments: str, timeout: int = 1800) -> dict[str, Any]:
    try:
        result = subprocess.run([sys.executable, "-m", module, *arguments], cwd=ROOT, capture_output=True, text=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"passed": False, "returncode": None, "errors": [{"type": type(exc).__name__, "message": str(exc)[:1000]}]}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"passed": False, "errors": [result.stdout[-2000:], result.stderr[-2000:]]}
    if isinstance(payload, dict):
        payload["returncode"] = result.returncode
        return payload
    return {"passed": False, "returncode": result.returncode, "errors": ["check did not return a JSON object"]}


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pilot_integrity() -> dict[str, Any]:
    path = ROOT / "experiments" / "results" / "executable-pilot-v0-5-0.jsonl"
    if not path.is_file():
        return {"passed": False, "reason": "pilot results file is missing"}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    errors: list[str] = []
    if len(rows) != 12:
        errors.append(f"pilot result count is {len(rows)}, expected 12")
    for row in rows:
        if row.get("terminal_outcome") == "INFRASTRUCTURE_ABORT":
            errors.append(f"infrastructure abort in {row.get('slot_id')}")
        if not row.get("log_path") or not Path(row["log_path"]).is_file():
            errors.append(f"missing log for {row.get('slot_id')}")
        if not row.get("receipt_path") or not Path(row["receipt_path"]).is_file():
            errors.append(f"missing receipt for {row.get('slot_id')}")
        if row.get("verifier_terminal_outcome") not in {"VALIDATED_SUCCESS", "VALIDATED_NON_SUCCESS", "UNKNOWN"}:
            errors.append(f"invalid verifier outcome for {row.get('slot_id')}")
    return {"passed": not errors, "row_count": len(rows), "errors": errors}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fail-closed overnight executable crypto/web study pipeline.")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--pilot-runs", type=int, default=1)
    parser.add_argument("--main-runs", type=int, default=3)
    parser.add_argument("--request-timeout", type=float, default=300.0)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--run-main", action="store_true", help="Continue to the 80-task main series after a clean pilot gate.")
    args = parser.parse_args(argv)
    if min(args.pilot_runs, args.main_runs, args.timeout_seconds, args.max_steps) <= 0 or args.request_timeout <= 0:
        parser.error("runs, timeouts, and max-steps must be positive")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = NIGHTLY_ROOT / f"{stamp}.json"
    report: dict[str, Any] = {"started_at": stamp, "benchmark_version": EXECUTABLE_BENCHMARK_VERSION, "model": args.model, "requested_main": args.run_main, "status": "PREFLIGHT"}
    _write_report(report_path, report)
    print(json.dumps({"event": "NIGHTLY_START", "report": str(report_path), "model": args.model, "benchmark_version": EXECUTABLE_BENCHMARK_VERSION}), flush=True)

    checks: dict[str, Any] = {}
    checks["ollama"] = _ollama_preflight(args.model)
    if checks["ollama"].get("passed") is not True:
        report.update({"status": "FAIL_CLOSED", "checks": checks, "reason": "Ollama model preflight failed"})
        _write_report(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path)}))
        return 2
    checks["catalog"] = _run_check("benchmark.validate_executable_catalog")
    if checks["catalog"].get("passed") is not True:
        report.update({"status": "FAIL_CLOSED", "checks": checks, "reason": "executable catalog validation failed"})
        _write_report(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path)}))
        return 2
    mapping = _run_check("benchmark.docker_mapping")
    checks["docker_mapping"] = mapping
    safety = _run_check("sandbox.safety_checks.run", "--json")
    checks["safety"] = safety
    image_ref = mapping.get("image_ref")
    safety_ok = safety.get("overall_passed") is True and safety.get("experiment_permitted") is True and safety.get("image_ref") == image_ref
    if not safety_ok:
        report.update({"status": "FAIL_CLOSED", "checks": checks, "reason": "Docker safety gate failed or image lock differs"})
        _write_report(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path)}))
        return 2
    report.update({"status": "PREFLIGHT_PASSED", "checks": checks})
    _write_report(report_path, report)

    smoke = _run_check("experiments.run_executable_smoke", "--model", args.model, "--request-timeout", str(args.request_timeout), timeout=max(1800, args.timeout_seconds + 300))
    report["smoke"] = smoke
    if smoke.get("returncode") != 0:
        report.update({"status": "FAIL_CLOSED", "reason": "Docker-backed provider smoke failed"})
        _write_report(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path)}))
        return 2

    report["status"] = "PILOT_RUNNING"
    _write_report(report_path, report)
    try:
        pilot = run_study(
            phase="pilot", model=args.model, runs_per_task=args.pilot_runs,
            request_timeout=args.request_timeout, timeout_seconds=args.timeout_seconds,
            max_steps=args.max_steps, pilot_families=("aead", "key-derivation", "sqli"),
            output_root=ROOT / "experiments",
        )
    except Exception as exc:
        report.update({"status": "PILOT_FAILED_CLOSED", "reason": f"{type(exc).__name__}: {str(exc)[:1000]}"})
        _write_report(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path)}))
        return 2
    report["pilot"] = pilot
    pilot_gate = _pilot_integrity()
    report["pilot_gate"] = pilot_gate
    if not pilot_gate.get("passed"):
        report.update({"status": "PILOT_GATE_FAILED", "reason": "pilot integrity gate failed; main not started"})
        _write_report(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path)}))
        return 2
    if not args.run_main:
        report.update({"status": "PILOT_COMPLETE_MAIN_NOT_STARTED"})
        _write_report(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path), "pilot": pilot}), flush=True)
        return 0

    report["status"] = "MAIN_RUNNING"
    _write_report(report_path, report)
    try:
        report["main"] = run_study(
            phase="main", model=args.model, runs_per_task=args.main_runs,
            request_timeout=args.request_timeout, timeout_seconds=args.timeout_seconds,
            max_steps=args.max_steps, pilot_families=(), output_root=ROOT / "experiments",
        )
    except Exception as exc:
        report.update({"status": "MAIN_INTERRUPTED_OR_FAILED", "reason": f"{type(exc).__name__}: {str(exc)[:1000]}"})
        _write_report(report_path, report)
        print(json.dumps({"status": report["status"], "report": str(report_path)}))
        return 2
    report["status"] = "MAIN_COMPLETE"
    report["finished_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write_report(report_path, report)
    print(json.dumps({"status": report["status"], "report": str(report_path), "main": report["main"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
