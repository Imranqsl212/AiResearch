"""Fail-closed reduced RAG study sized for one Apple-silicon overnight run.

This is an explicitly exploratory profile.  It preserves complete
RD/UD/RW/UW x retrieval-off/relevant blocks, but samples fewer families and
uses one run per arm.  Its results must not be presented as the preregistered
full repeated-run study or used for confirmatory GEE claims.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from benchmark.executable_catalog import EXECUTABLE_BENCHMARK_VERSION
from benchmark.retrieval import MODES, augment_task
from experiments.accounting import write_snapshot
from experiments.run_executable_study import ROOT, load_catalog, run_study, select_tasks
from experiments.run_nightly_study import _ollama_preflight, _run_check, _write_report
from experiments.run_rag_factorial_study import validate_retrieval_design
from experiments.validate_artifacts import validate_artifacts


PROFILE_VERSION = "2.0.0"
EXPERIMENT_PREFIX = "rag-overnight-v2"
PILOT_FAMILIES = ("aead",)
MAIN_FAMILIES = ("key-derivation", "nonce", "weak-randomness", "sqli", "xss")
EXPECTED_CONDITIONS = {"RD", "UD", "RW", "UW"}


def build_profile_tasks(families: Sequence[str]) -> list[dict[str, Any]]:
    """Build complete eight-arm blocks for only the declared families."""

    requested = tuple(families)
    if not requested or len(set(requested)) != len(requested):
        raise ValueError("profile families must be nonempty and unique")
    base = select_tasks(load_catalog(), "pilot", requested)
    rows = [augment_task(task, mode) for task in base for mode in sorted(MODES)]
    for family in requested:
        block = [row for row in rows if row["family"] == family]
        if len(block) != 8:
            raise ValueError(f"family {family!r} has {len(block)} arms, expected 8")
        if {row["condition"] for row in block} != EXPECTED_CONDITIONS:
            raise ValueError(f"family {family!r} lacks a complete condition block")
        if {row["retrieval_mode"] for row in block} != set(MODES):
            raise ValueError(f"family {family!r} lacks a complete retrieval block")
    return sorted(rows, key=lambda row: str(row["task_id"]))


def validate_profile() -> dict[str, Any]:
    pilot = build_profile_tasks(PILOT_FAMILIES)
    main = build_profile_tasks(MAIN_FAMILIES)
    pilot_ids = {str(row["base_task_id"]) for row in pilot}
    main_ids = {str(row["base_task_id"]) for row in main}
    domains = {str(row["domain"]) for row in main}
    errors: list[str] = []
    if len(pilot) != 8:
        errors.append(f"pilot has {len(pilot)} arms, expected 8")
    if len(main) != 40:
        errors.append(f"main has {len(main)} arms, expected 40")
    if pilot_ids & main_ids:
        errors.append("pilot and main base tasks overlap")
    if domains != {"crypto", "web"}:
        errors.append(f"main domains are incomplete: {sorted(domains)}")
    return {
        "passed": not errors,
        "profile_version": PROFILE_VERSION,
        "exploratory": True,
        "pilot_families": list(PILOT_FAMILIES),
        "main_families": list(MAIN_FAMILIES),
        "pilot_arms": len(pilot),
        "main_arms": len(main),
        "runs_per_arm": 1,
        "errors": errors,
    }


def _integrity_gate(results_path: Path, expected_rows: int) -> dict[str, Any]:
    if not results_path.is_file():
        return {"passed": False, "row_count": 0, "errors": ["result file is missing"]}
    rows = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    errors: list[str] = []
    if len(rows) != expected_rows:
        errors.append(f"result count is {len(rows)}, expected {expected_rows}")
    if {row.get("retrieval_mode") for row in rows} != set(MODES):
        errors.append("retrieval arms are incomplete")
    for row in rows:
        slot = row.get("slot_id")
        if row.get("terminal_outcome") == "INFRASTRUCTURE_ABORT":
            errors.append(f"infrastructure abort in {slot}")
        for field in ("log_path", "receipt_path"):
            value = row.get(field)
            if not isinstance(value, str) or not Path(value).is_file():
                errors.append(f"missing {field} for {slot}")
        log, receipt = row.get("log_path"), row.get("receipt_path")
        if isinstance(log, str) and isinstance(receipt, str) and Path(log).is_file() and Path(receipt).is_file():
            experiment_id = row.get("experiment_id")
            if not isinstance(experiment_id, str):
                errors.append(f"missing experiment_id for {slot}")
                continue
            integrity = validate_artifacts(
                manifest_path=ROOT / "experiments" / "manifests" / f"{experiment_id}.json",
                log_path=Path(log), receipt_path=Path(receipt),
                require_git=True, require_action_verifier=True,
            )
            if not integrity["passed"]:
                errors.append(f"artifact integrity failed for {slot}: {integrity['errors']}")
    return {"passed": not errors, "row_count": len(rows), "errors": errors}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the fail-closed 8-pilot + 40-main exploratory overnight profile."
    )
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--request-timeout", type=float, default=600.0)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--run-main", action="store_true")
    args = parser.parse_args(argv)
    if min(args.request_timeout, args.timeout_seconds, args.max_steps) <= 0:
        parser.error("timeouts and max-steps must be positive")
    if args.request_timeout >= args.timeout_seconds:
        parser.error("episode timeout must exceed one Ollama request timeout")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = ROOT / "experiments" / "nightly" / f"rag-overnight-{stamp}.json"
    report: dict[str, Any] = {
        "started_at": stamp,
        "status": "PREFLIGHT",
        "profile": validate_profile(),
        "profile_version": PROFILE_VERSION,
        "exploratory": True,
        "benchmark_version": EXECUTABLE_BENCHMARK_VERSION,
        "model": args.model,
        "requested_main": args.run_main,
        "provider_request_timeout_seconds": args.request_timeout,
        "episode_timeout_seconds": args.timeout_seconds,
        "deviations_from_confirmatory_protocol": [
            "one run per arm",
            "five main families rather than the full twenty-family catalog",
            f"maximum {args.max_steps} steps",
            "results are exploratory and do not support confirmatory GEE claims",
        ],
    }
    _write_report(report_path, report)
    print(json.dumps({"event": "OVERNIGHT_START", "report": str(report_path)}), flush=True)
    report["historical_accounting_snapshot"] = str(write_snapshot())
    _write_report(report_path, report)

    checks = {
        "ollama": _ollama_preflight(args.model),
        "catalog": _run_check("benchmark.validate_executable_catalog"),
        "retrieval": validate_retrieval_design(),
        "profile": report["profile"],
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
    pilot_tasks = build_profile_tasks(PILOT_FAMILIES)
    try:
        report["pilot"] = run_study(
            phase="pilot", model=args.model, runs_per_task=1,
            request_timeout=args.request_timeout, timeout_seconds=args.timeout_seconds,
            max_steps=args.max_steps, pilot_families=PILOT_FAMILIES,
            output_root=ROOT / "experiments", task_rows=pilot_tasks,
            experiment_prefix=EXPERIMENT_PREFIX,
            fail_on_infrastructure_abort=True,
        )
    except Exception as exc:
        report.update({"status": "PILOT_FAILED_CLOSED", "reason": f"{type(exc).__name__}: {str(exc)[:1000]}"})
        report["latest_accounting_snapshot"] = str(write_snapshot())
        _write_report(report_path, report)
        return 2

    suffix = EXECUTABLE_BENCHMARK_VERSION.replace(".", "-")
    pilot_results = ROOT / "experiments" / "results" / f"{EXPERIMENT_PREFIX}-pilot-{suffix}.jsonl"
    pilot_gate = _integrity_gate(pilot_results, expected_rows=8)
    report["pilot_gate"] = pilot_gate
    report["latest_accounting_snapshot"] = str(write_snapshot())
    if not pilot_gate["passed"]:
        report.update({"status": "PILOT_GATE_FAILED", "reason": "main remains blocked"})
        _write_report(report_path, report)
        return 2
    if not args.run_main:
        report["status"] = "PILOT_COMPLETE_MAIN_NOT_STARTED"
        _write_report(report_path, report)
        return 0

    report["status"] = "MAIN_RUNNING"
    _write_report(report_path, report)
    main_tasks = build_profile_tasks(MAIN_FAMILIES)
    try:
        report["main"] = run_study(
            phase="main", model=args.model, runs_per_task=1,
            request_timeout=args.request_timeout, timeout_seconds=args.timeout_seconds,
            max_steps=args.max_steps, pilot_families=(),
            output_root=ROOT / "experiments", task_rows=main_tasks,
            experiment_prefix=EXPERIMENT_PREFIX,
            fail_on_infrastructure_abort=True,
        )
    except Exception as exc:
        report.update({"status": "MAIN_INTERRUPTED_OR_FAILED", "reason": f"{type(exc).__name__}: {str(exc)[:1000]}"})
        report["latest_accounting_snapshot"] = str(write_snapshot())
        _write_report(report_path, report)
        return 2

    main_results = ROOT / "experiments" / "results" / f"{EXPERIMENT_PREFIX}-main-{suffix}.jsonl"
    main_gate = _integrity_gate(main_results, expected_rows=40)
    report["main_gate"] = main_gate
    report["latest_accounting_snapshot"] = str(write_snapshot())
    report["status"] = "MAIN_COMPLETE" if main_gate["passed"] else "MAIN_INTEGRITY_FAILED"
    report["finished_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write_report(report_path, report)
    return 0 if main_gate["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
