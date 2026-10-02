"""Fail-closed one-command launcher for the RAG factorial pilot and optional main run."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from benchmark.executable_catalog import EXECUTABLE_BENCHMARK_VERSION
from experiments.run_executable_study import ROOT, run_study
from experiments.run_nightly_study import _ollama_preflight, _run_check, _write_report
from experiments.run_rag_factorial_study import (
    EXPERIMENT_PREFIX,
    PILOT_FAMILIES,
    build_factorial_tasks,
    validate_retrieval_design,
)


def _pilot_gate(results_path: Path, runs_per_arm: int) -> dict[str, Any]:
    if not results_path.is_file():
        return {"passed": False, "errors": ["pilot result file is missing"]}
    rows = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected = 24 * runs_per_arm
    errors: list[str] = []
    if len(rows) != expected:
        errors.append(f"pilot result count is {len(rows)}, expected {expected}")
    modes = {row.get("retrieval_mode") for row in rows}
    if modes != {"off", "relevant"}:
        errors.append(f"retrieval arms are incomplete: {sorted(str(item) for item in modes)}")
    for row in rows:
        if row.get("terminal_outcome") == "INFRASTRUCTURE_ABORT":
            errors.append(f"infrastructure abort in {row.get('slot_id')}")
        for field in ("log_path", "receipt_path"):
            path = row.get(field)
            if not isinstance(path, str) or not Path(path).is_file():
                errors.append(f"missing {field} for {row.get('slot_id')}")
    return {"passed": not errors, "row_count": len(rows), "errors": errors}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run safety gates, smoke, RAG-factorial pilot, and optionally main."
    )
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--pilot-runs", type=int, default=1)
    parser.add_argument("--main-runs", type=int, default=3)
    parser.add_argument("--request-timeout", type=float, default=300.0)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--run-main", action="store_true")
    args = parser.parse_args(argv)
    if min(args.pilot_runs, args.main_runs, args.timeout_seconds, args.max_steps) <= 0 or args.request_timeout <= 0:
        parser.error("run counts, timeouts, and max-steps must be positive")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = ROOT / "experiments" / "nightly" / f"rag-{stamp}.json"
    report: dict[str, Any] = {
        "started_at": stamp,
        "status": "PREFLIGHT",
        "study": "rag_feedback_feasibility_factorial",
        "benchmark_version": EXECUTABLE_BENCHMARK_VERSION,
        "model": args.model,
        "requested_main": args.run_main,
    }
    _write_report(report_path, report)
    print(json.dumps({"event": "RAG_NIGHTLY_START", "report": str(report_path)}), flush=True)

    checks = {
        "ollama": _ollama_preflight(args.model),
        "catalog": _run_check("benchmark.validate_executable_catalog"),
        "retrieval": validate_retrieval_design(),
    }
    if not all(check.get("passed") is True for check in checks.values()):
        report.update({"status": "FAIL_CLOSED", "checks": checks, "reason": "static preflight failed"})
        _write_report(report_path, report)
        return 2
    checks["docker_mapping"] = _run_check("benchmark.docker_mapping")
    checks["safety"] = _run_check("sandbox.safety_checks.run", "--json")
    mapping_image = checks["docker_mapping"].get("image_ref")
    safety = checks["safety"]
    if not (
        checks["docker_mapping"].get("passed") is True
        and safety.get("overall_passed") is True
        and safety.get("experiment_permitted") is True
        and safety.get("image_ref") == mapping_image
    ):
        report.update({"status": "FAIL_CLOSED", "checks": checks, "reason": "Docker safety/image gate failed"})
        _write_report(report_path, report)
        return 2

    smoke = _run_check(
        "experiments.run_executable_smoke",
        "--model", args.model,
        "--request-timeout", str(args.request_timeout),
        timeout=max(1800, args.timeout_seconds + 300),
    )
    report.update({"checks": checks, "smoke": smoke})
    if smoke.get("returncode") != 0:
        report.update({"status": "FAIL_CLOSED", "reason": "provider/Docker smoke failed"})
        _write_report(report_path, report)
        return 2

    report["status"] = "PILOT_RUNNING"
    _write_report(report_path, report)
    try:
        pilot_tasks = build_factorial_tasks(phase="pilot", pilot_families=PILOT_FAMILIES)
        pilot = run_study(
            phase="pilot", model=args.model, runs_per_task=args.pilot_runs,
            request_timeout=args.request_timeout, timeout_seconds=args.timeout_seconds,
            max_steps=args.max_steps, pilot_families=PILOT_FAMILIES,
            output_root=ROOT / "experiments", task_rows=pilot_tasks,
            experiment_prefix=EXPERIMENT_PREFIX,
        )
    except Exception as exc:
        report.update({"status": "PILOT_FAILED_CLOSED", "reason": f"{type(exc).__name__}: {str(exc)[:1000]}"})
        _write_report(report_path, report)
        return 2
    results_path = ROOT / "experiments" / "results" / f"{EXPERIMENT_PREFIX}-pilot-{EXECUTABLE_BENCHMARK_VERSION.replace('.', '-')}.jsonl"
    gate = _pilot_gate(results_path, args.pilot_runs)
    report.update({"pilot": pilot, "pilot_gate": gate})
    if not gate["passed"]:
        report.update({"status": "PILOT_GATE_FAILED", "reason": "main remains blocked"})
        _write_report(report_path, report)
        return 2
    if not args.run_main:
        report["status"] = "PILOT_COMPLETE_MAIN_NOT_STARTED"
        _write_report(report_path, report)
        return 0

    report["status"] = "MAIN_RUNNING"
    _write_report(report_path, report)
    try:
        main_tasks = build_factorial_tasks(phase="main", pilot_families=())
        report["main"] = run_study(
            phase="main", model=args.model, runs_per_task=args.main_runs,
            request_timeout=args.request_timeout, timeout_seconds=args.timeout_seconds,
            max_steps=args.max_steps, pilot_families=(),
            output_root=ROOT / "experiments", task_rows=main_tasks,
            experiment_prefix=EXPERIMENT_PREFIX,
        )
    except Exception as exc:
        report.update({"status": "MAIN_INTERRUPTED_OR_FAILED", "reason": f"{type(exc).__name__}: {str(exc)[:1000]}"})
        _write_report(report_path, report)
        return 2
    report["status"] = "MAIN_COMPLETE"
    report["finished_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write_report(report_path, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
