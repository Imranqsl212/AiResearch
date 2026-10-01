"""Fail-closed overnight readiness runner.

It validates local prerequisites and refuses agent execution until candidate code is
executed inside the approved isolated runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from experiments.run_family_smoke_batch import FAMILIES
from experiments.run_family_smoke import run_smoke


ROOT = Path(__file__).resolve().parents[1]


def _run_check(module: str, *arguments: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", module, *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"passed": False, "errors": [{"type": type(exc).__name__, "message": str(exc)[:1000]}]}
    try: payload = json.loads(result.stdout)
    except json.JSONDecodeError: payload = {"passed": False, "errors": [result.stdout[-2000:], result.stderr[-2000:]]}
    payload["returncode"] = result.returncode
    return payload


def _ollama_preflight(model: str) -> dict[str, Any]:
    """Confirm the requested model is available from the local Ollama API only."""

    request = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"passed": False, "endpoint": "http://127.0.0.1:11434", "model": model,
                "error": f"local Ollama preflight failed: {type(exc).__name__}: {str(exc)[:500]}"}
    available = [item.get("name") for item in payload.get("models", []) if isinstance(item, dict)]
    return {"passed": model in available, "endpoint": "http://127.0.0.1:11434", "model": model,
            "available_models": available,
            "error": None if model in available else f"requested model {model!r} is not installed locally"}


def _load_completed(path: Path) -> dict[str, dict[str, Any]]:
    completed = {}
    if not path.is_file(): return completed
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            key = f"{row.get('domain')}/{row.get('family')}"
            log_path = Path(row.get("log_path", ""))
            receipt_path = Path(row.get("receipt_path", ""))
            if not key or row.get("errors") != [] or not isinstance(row.get("verifier"), dict):
                continue
            if row.get("steps", 0) < 1 or not log_path.is_file() or not receipt_path.is_file():
                continue
            raw_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            actual_hash = hashlib.sha256(log_path.read_bytes()).hexdigest()
            if raw_receipt.get("log_sha256") != actual_hash or row.get("log_sha256") != actual_hash:
                continue
            if raw_receipt.get("run_id") != row.get("run_id"):
                continue
            completed[key] = row
        except json.JSONDecodeError: continue
        except OSError: continue
    return completed


def _next_run_id(run_root: Path, domain: str, family: str, index: int) -> str:
    """Return a run id whose raw log and receipt paths are unused."""

    experiment_id = f"{domain}-{family}-ollama-smoke-excluded-v0.4.0"
    base = f"overnight-{run_root.name}-{index:02d}"
    for attempt in range(1, 10_000):
        suffix = "" if attempt == 1 else f"-retry{attempt:03d}"
        candidate = f"{base}{suffix}"
        if not (run_root / "runs" / experiment_id / f"{candidate}.jsonl").exists() and not (
            run_root / "runs" / experiment_id / f"{candidate}.receipt.json"
        ).exists():
            return candidate
    raise RuntimeError(f"could not allocate a unique run id for {domain}/{family}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run validation and resumable local Ollama family smokes overnight.")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--request-timeout", type=float, default=300, help="per-Ollama-call timeout; smoke episode budget is 900s")
    parser.add_argument("--output-root", type=Path, default=ROOT / "experiments" / "overnight")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="reuse one existing overnight directory; completed family rows are skipped",
    )
    parser.add_argument("--no-smoke", action="store_true")
    args = parser.parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_root = args.run_dir if args.run_dir is not None else args.output_root / stamp
    run_root.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"started_at": stamp, "model": args.model, "request_timeout": args.request_timeout, "checks": {}, "smokes": [], "pilot": {"started": False, "status": "BLOCKED_UNTIL_SMOKE_GATE_AND_CONDITION_AWARE_SCHEDULER"}}
    print(json.dumps({"event": "RUN_DIR", "run_dir": str(run_root), "model": args.model, "family_count": len(FAMILIES)}), flush=True)
    (run_root / "overnight_progress.json").write_text(json.dumps({**report, "status": "PREFLIGHT_RUNNING"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    preflight = _ollama_preflight(args.model)
    report["checks"]["ollama_preflight"] = preflight
    if preflight.get("passed") is not True:
        report["status"] = "FAIL_CLOSED"
        report_path = run_root / "overnight_report.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAIL_CLOSED", "reason": preflight.get("error"), "report": str(report_path)}))
        return 1
    for module in ("benchmark.validate_executable_catalog", "benchmark.docker_mapping", "benchmark.web_mapping"):
        check = _run_check(module); report["checks"][module] = check
        if check.get("passed") is not True:
            (run_root / "overnight_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"status": "FAIL_CLOSED", "failed_check": module, "report": str(run_root / 'overnight_report.json')})); return 1
    if not args.no_smoke:
        report["checks"]["candidate_execution_isolation"] = {"status": "PENDING_OFFICIAL_SAFETY_SUITE"}
    safety = _run_check("sandbox.safety_checks.run", "--json")
    expected_image = report["checks"]["benchmark.docker_mapping"].get("image_ref")
    safety_passed = (
        safety.get("overall_passed") is True
        and safety.get("experiment_permitted") is True
        and safety.get("image_ref") == expected_image
        and safety.get("image_config_digest") == expected_image.rsplit("@", 1)[-1]
    )
    report["checks"]["docker_safety"] = {"passed": safety_passed, "result": safety}
    report["checks"]["candidate_execution_isolation"] = {
        "passed": safety_passed and any(
            check.get("check_id") == "candidate_runtime_isolated" and check.get("passed") is True
            for check in safety.get("checks", [])
        ),
        "status": "PASS" if safety_passed else "BLOCKED",
        "detail": "The scored candidate path is Docker-isolated and covered by the fresh official safety receipt." if safety_passed else "Fresh official safety suite did not prove the candidate runtime.",
    }
    if not safety_passed:
        report["status"] = "FAIL_CLOSED"
        report_path = run_root / "overnight_report.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAIL_CLOSED", "reason": "fresh Docker runtime safety suite failed or image digest mismatched", "report": str(report_path)}))
        return 1
    if not args.no_smoke:
        summary_path = run_root / "family_smoke_results.jsonl"
        completed = _load_completed(summary_path)
        smoke_results = [completed[key] for key in (f"{domain}/{family}" for domain, family in FAMILIES) if key in completed]
        for index, (domain, family) in enumerate(FAMILIES, 1):
            key = f"{domain}/{family}"
            if key in completed:
                print(f"SKIP {key} (completed receipt already present)", flush=True)
                continue
            run_id = _next_run_id(run_root, domain, family, index)
            print(f"START {key} {run_id}", flush=True)
            report["current_family"] = key
            report["status"] = "RUNNING"
            (run_root / "overnight_progress.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = run_smoke(domain=domain, family=family, output_root=run_root, model=args.model, run_id=run_id, request_timeout=args.request_timeout)
            with summary_path.open("a", encoding="utf-8") as handle: handle.write(json.dumps(result, sort_keys=True) + "\n")
            smoke_results.append(result)
            report["smokes"] = smoke_results
            report["status"] = "RUNNING"
            (run_root / "overnight_progress.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"family": key, "terminal_outcome": result["terminal_outcome"], "verifier": bool(result.get("verifier")), "errors": result["errors"]}), flush=True)
        report["smokes"] = smoke_results
    smoke_gate = (
        len(report["smokes"]) == len(FAMILIES)
        and all(
            item.get("errors") == []
            and isinstance(item.get("verifier"), dict)
            and item.get("steps", 0) >= 1
            and Path(item.get("log_path", "")).is_file()
            and Path(item.get("receipt_path", "")).is_file()
            for item in report["smokes"]
        )
        if not args.no_smoke
        else False
    )
    report["status"] = "SMOKE_GATE_PASSED_PILOT_NOT_STARTED" if smoke_gate else "SMOKE_GATE_NOT_PASSED"
    report.pop("current_family", None)
    report["pilot"]["smoke_gate_passed"] = smoke_gate
    report["finished_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report_path = run_root / "overnight_report.json"; report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_root / "overnight_progress.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(report_path), "run_dir": str(run_root), "smoke_count": len(report["smokes"]), "resumable": True}))
    return 0 if smoke_gate else 2


if __name__ == "__main__": raise SystemExit(main())
