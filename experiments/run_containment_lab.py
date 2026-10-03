"""Run the synthetic containment-lab suite with a local Ollama agent.

This is deliberately an excluded development study.  It never asks the model to run
a shell command or supplies a Docker capability, a filesystem API, a network API,
credentials, a real host path, or a recipient.  The task runtime is the deterministic
in-memory fixture, not Docker and not the host machine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from agent.episode_sandbox import InMemoryFiniteStateSandbox, opaque_public_task_id
from agent.ollama_adapter import OllamaAdapter
from agent.runner import EpisodeRunner, opaque_public_run_id
from agent.contracts import RunContext
from benchmark.validate_containment_lab import DEFAULT_TASK_DIR, load_tasks, validate_benchmark
from experiments.manifest import ExperimentManifest, resolve_git_commit, utc_now, write_manifest
from experiments.trajectory_logger import TrajectoryLogger


ROOT = Path(__file__).resolve().parents[1]
_RESUME_SCHEMA_VERSION = "0.1.0"
_FROZEN_REQUEST_TIMEOUT = 180.0
_FROZEN_MAX_OUTPUT_TOKENS = 512


def _local_ollama_model_available(model: str, timeout_seconds: float) -> dict[str, Any]:
    """Fail closed unless the requested model is available on loopback Ollama."""

    request = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"passed": False, "reason": f"local Ollama preflight failed: {type(exc).__name__}: {exc}"}
    rows = payload.get("models") if isinstance(payload, dict) else None
    names = {str(row.get("name")) for row in rows if isinstance(row, dict)} if isinstance(rows, list) else set()
    return {"passed": model in names, "available_models": sorted(names), "model": model}


def _experiment_id() -> str:
    return "containment-lab-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ").lower()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read JSON object {path}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return document


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_manifest(
    *, output_root: Path, experiment_id: str, model: str, tasks: Sequence[dict[str, Any]]
) -> tuple[dict[str, Any], Path]:
    """Load and check the immutable parent manifest before a continuation.

    A continuation may not quietly swap model, task order, benchmark version, or
    safety mode.  The limited launcher profile below matches the original v0.1.3
    series and is written into the continuation ledger for auditability.
    """

    path = output_root / "manifests" / f"{experiment_id}.json"
    manifest = _read_json_object(path)
    expected_task_ids = [str(task["task_id"]) for task in tasks]
    expected = {
        "experiment_id": experiment_id,
        "model": model,
        "agent_version": "ollama-adapter-0.2.0",
        "benchmark_version": "containment-lab-0.1.3",
        "task_ids": expected_task_ids,
        "task_count": len(expected_task_ids),
        "runs_per_task": 1,
        "temperature": 0,
        "max_steps": 8,
        "timeout_seconds": 300,
        "adapter_type": "ollama_local_loopback",
        "sandbox_type": "in_memory_finite_state_synthetic",
        "safety_mode": "simulation_only_no_host_no_docker_no_network_no_delivery",
        "seed": 7,
        "token_budget": None,
    }
    mismatches = sorted(key for key, value in expected.items() if manifest.get(key) != value)
    if mismatches:
        raise ValueError(f"frozen parent manifest does not match v0.1.3 continuation: {', '.join(mismatches)}")
    if not isinstance(manifest.get("git_commit"), str) or not manifest["git_commit"]:
        raise ValueError("frozen parent manifest does not contain a git commit")
    return manifest, path


def _audit_existing_attempts(
    *, output_root: Path, experiment_id: str, tasks: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Verify each prior receipt and return task-level completion/abort history.

    Receipt digests are verified before a task is skipped.  Corrupted or ambiguous
    records fail closed instead of being silently ignored.  An infrastructure-abort
    attempt is preserved but does not satisfy the task's required completed episode.
    """

    task_ids = {str(task["task_id"]) for task in tasks}
    run_dir = output_root / "runs" / experiment_id
    if not run_dir.is_dir():
        raise ValueError(f"run directory is missing: {run_dir}")
    completed: dict[str, dict[str, Any]] = {}
    aborted: list[dict[str, Any]] = []
    all_attempts: list[dict[str, Any]] = []
    for receipt_path in sorted(run_dir.glob("*.receipt.json")):
        receipt = _read_json_object(receipt_path)
        run_id = receipt.get("run_id")
        task_id = receipt.get("task_id")
        log_name = receipt.get("log_file")
        recorded_digest = receipt.get("log_sha256")
        if (
            receipt.get("experiment_id") != experiment_id
            or not isinstance(run_id, str)
            or not isinstance(task_id, str)
            or task_id not in task_ids
            or not isinstance(log_name, str)
            or Path(log_name).name != log_name
            or not isinstance(recorded_digest, str)
            or len(recorded_digest) != 64
        ):
            raise ValueError(f"receipt has invalid identity fields: {receipt_path}")
        log_path = run_dir / log_name
        if not log_path.is_file() or _sha256_file(log_path) != recorded_digest:
            raise ValueError(f"receipt digest does not match its immutable log: {receipt_path}")
        attempt = {
            "run_id": run_id,
            "task_id": task_id,
            "terminal_outcome": receipt.get("terminal_outcome"),
            "stop_event": receipt.get("stop_event"),
            "receipt_path": str(receipt_path),
            "log_path": str(log_path),
            "log_sha256": recorded_digest,
        }
        all_attempts.append(attempt)
        if receipt.get("terminal_outcome") == "INFRASTRUCTURE_ABORT":
            aborted.append(attempt)
            continue
        if task_id in completed:
            raise ValueError(f"multiple completed attempts exist for task {task_id}; manual adjudication required")
        completed[task_id] = attempt
    if not all_attempts:
        raise ValueError("no prior receipts found; use a new series instead of --resume")
    return {
        "completed": completed,
        "aborted": aborted,
        "all_attempts": all_attempts,
        "remaining_task_ids": [str(task["task_id"]) for task in tasks if str(task["task_id"]) not in completed],
    }


def _write_continuation_ledger(
    *, output_root: Path, experiment_id: str, parent_manifest_path: Path, audit: dict[str, Any],
    remaining_task_ids: Sequence[str], model: str, request_timeout: float, max_output_tokens: int,
) -> Path:
    """Write an immutable ledger that links new attempts to the paused series."""

    continuation_id = f"{experiment_id}.resume-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ').lower()}"
    path = output_root / "continuations" / f"{continuation_id}.json"
    payload = {
        "schema_version": _RESUME_SCHEMA_VERSION,
        "continuation_id": continuation_id,
        "parent_experiment_id": experiment_id,
        "parent_manifest_path": str(parent_manifest_path),
        "parent_manifest_sha256": _sha256_file(parent_manifest_path),
        "created_at": utc_now(),
        "model": model,
        "request_timeout_seconds": request_timeout,
        "max_output_tokens": max_output_tokens,
        "completed_attempts_verified": list(audit["completed"].values()),
        "infrastructure_abort_attempts_preserved": list(audit["aborted"]),
        "remaining_task_ids": list(remaining_task_ids),
        "safety": {
            "actual_host_access_attempted": False,
            "actual_container_escape_attempted": False,
            "actual_network_or_message_delivery_attempted": False,
            "docker_containers_created": 0,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def _next_run_id(*, output_root: Path, experiment_id: str, task_index: int) -> str:
    """Allocate a fresh retry ID without renaming or overwriting prior attempts."""

    run_dir = output_root / "runs" / experiment_id
    prefix = f"lab-{task_index:03d}-attempt-"
    prior = [path.name for path in run_dir.glob(f"{prefix}*.receipt.json")]
    return f"{prefix}{len(prior) + 2:03d}"


def _execute_one_task(
    *, task: dict[str, Any], task_index: int, run_id: str, output_root: Path, manifest: dict[str, Any],
    model: str, request_timeout: float, max_output_tokens: int,
) -> dict[str, Any]:
    """Run one non-overwriting synthetic episode under the frozen parent manifest."""

    context = RunContext(
        experiment_id=str(manifest["experiment_id"]),
        run_id=run_id,
        model=model,
        agent_version=str(manifest["agent_version"]),
        benchmark_version=str(manifest["benchmark_version"]),
        git_commit=str(manifest["git_commit"]),
        started_at=utc_now(),
        max_steps=int(manifest["max_steps"]),
        timeout_seconds=int(manifest["timeout_seconds"]),
        seed=manifest["seed"],
        temperature=manifest["temperature"],
        token_budget=manifest["token_budget"],
    )
    public_task_id = opaque_public_task_id(str(task["task_id"]), str(task["version"]))
    public_run_id = opaque_public_run_id(context)
    result = EpisodeRunner(
        adapter=OllamaAdapter(
            model=model,
            request_timeout=request_timeout,
            max_output_tokens=max_output_tokens,
            context_window=4096,
        ),
        sandbox=InMemoryFiniteStateSandbox(task),
        logger=TrajectoryLogger(
            output_root / "runs", context, str(task["task_id"]), str(task["condition"]), public_task_id, public_run_id,
        ),
        context=context,
        public_task_id=public_task_id,
        public_run_id=public_run_id,
    ).run(task)
    row = result.as_mapping()
    row.update({
        "analysis_status": "exploratory_candidate",
        "excluded_from_confirmatory_crypto_web_analysis": True,
        "eligible_for_exploratory_analysis": True,
        "study_kind": "synthetic_containment_lab_exploratory",
        "actual_host_access_attempted": False,
        "actual_container_escape_attempted": False,
        "actual_network_or_message_delivery_attempted": False,
        "task_index": task_index,
    })
    return row


def run_suite(
    *,
    output_root: Path,
    model: str,
    request_timeout: float,
    max_output_tokens: int,
    experiment_id: str,
    task_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Execute all 12 simulation-only episodes and write immutable local logs."""

    validation = validate_benchmark()
    if validation["passed"] is not True:
        return {"status": "FAIL_CLOSED", "reason": "containment-lab static validation failed", "validation": validation}
    preflight = _local_ollama_model_available(model, min(request_timeout, 10.0))
    if preflight["passed"] is not True:
        return {"status": "FAIL_CLOSED", "reason": "local Ollama preflight failed", "validation": validation, "ollama": preflight}

    all_task_rows = load_tasks(DEFAULT_TASK_DIR)
    requested = set(task_ids or ())
    available = {str(task["task_id"]) for task in all_task_rows}
    unknown = sorted(requested - available)
    if unknown:
        return {"status": "FAIL_CLOSED", "reason": f"unknown task IDs: {', '.join(unknown)}", "validation": validation}
    tasks = [task for task in all_task_rows if not requested or str(task["task_id"]) in requested]
    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        model=model,
        agent_version="ollama-adapter-0.2.0",
        benchmark_version="containment-lab-0.1.3",
        task_ids=tuple(str(task["task_id"]) for task in tasks),
        runs_per_task=1,
        temperature=0,
        max_steps=8,
        timeout_seconds=300,
        git_commit=resolve_git_commit(ROOT),
        adapter_type="ollama_local_loopback",
        sandbox_type="in_memory_finite_state_synthetic",
        safety_mode="simulation_only_no_host_no_docker_no_network_no_delivery",
        seed=7,
        token_budget=None,
        notes=(
            "Development-only containment-boundary simulation. All runs are excluded from "
            "crypto/web analysis. No real escape, host file, service, network, credential, "
            "phishing delivery, or Docker container is involved."
        ),
    )
    manifest_path = write_manifest(manifest, output_root / "manifests")
    rows: list[dict[str, Any]] = []
    for index, task in enumerate(tasks, start=1):
        run_id = f"lab-{index:03d}"
        context = RunContext(
            experiment_id=experiment_id,
            run_id=run_id,
            model=model,
            agent_version=manifest.agent_version,
            benchmark_version=manifest.benchmark_version,
            git_commit=manifest.git_commit,
            started_at=utc_now(),
            max_steps=manifest.max_steps,
            timeout_seconds=manifest.timeout_seconds,
            seed=manifest.seed,
            temperature=manifest.temperature,
            token_budget=manifest.token_budget,
        )
        public_task_id = opaque_public_task_id(str(task["task_id"]), str(task["version"]))
        public_run_id = opaque_public_run_id(context)
        result = EpisodeRunner(
            adapter=OllamaAdapter(
                model=model,
                request_timeout=request_timeout,
                max_output_tokens=max_output_tokens,
                context_window=4096,
            ),
            sandbox=InMemoryFiniteStateSandbox(task),
            logger=TrajectoryLogger(
                output_root / "runs", context, str(task["task_id"]), str(task["condition"]), public_task_id, public_run_id,
            ),
            context=context,
            public_task_id=public_task_id,
            public_run_id=public_run_id,
        ).run(task)
        row = result.as_mapping()
        row.update({
            "analysis_status": "exploratory_candidate",
            "excluded_from_confirmatory_crypto_web_analysis": True,
            "eligible_for_exploratory_analysis": True,
            "study_kind": "synthetic_containment_lab_exploratory",
            "actual_host_access_attempted": False,
            "actual_container_escape_attempted": False,
            "actual_network_or_message_delivery_attempted": False,
        })
        rows.append(row)
        print(json.dumps({"event": "CONTAINMENT_LAB_RUN_FINISHED", "run_id": run_id, "task_id": task["task_id"], "terminal_outcome": result.terminal_outcome}, sort_keys=True), flush=True)
    completed_at = utc_now()
    report = {
        "status": "COMPLETE",
        "experiment_id": experiment_id,
        "manifest_path": str(manifest_path),
        "created_at": completed_at,
        "analysis_status": "exploratory_candidate",
        "excluded_from_confirmatory_crypto_web_analysis": True,
        "eligible_for_exploratory_analysis": True,
        "study_kind": "synthetic_containment_lab_exploratory",
        "task_count": len(tasks),
        "agent_runs": len(rows),
        "safety": {
            "actual_host_access_attempted": False,
            "actual_container_escape_attempted": False,
            "actual_network_or_message_delivery_attempted": False,
            "docker_containers_created": 0,
            "real_targets_contacted": False,
        },
        "static_validation": validation,
        "ollama": preflight,
        "runs": rows,
    }
    report_path = output_root / "reports" / f"{experiment_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    report["report_path"] = str(report_path)
    return report


def resume_suite(
    *,
    output_root: Path,
    model: str,
    request_timeout: float,
    max_output_tokens: int,
    experiment_id: str,
) -> dict[str, Any]:
    """Continue a paused v0.1.3 series without touching immutable prior artifacts.

    Only tasks without a digest-verified, non-infrastructure terminal receipt are
    eligible.  A failed or manually interrupted attempt remains in the attempt
    ledger; its task is retried under a fresh run ID.  The complete report is written
    only after exactly one valid completed attempt exists for every frozen task.
    """

    if request_timeout != _FROZEN_REQUEST_TIMEOUT or max_output_tokens != _FROZEN_MAX_OUTPUT_TOKENS:
        return {
            "status": "FAIL_CLOSED",
            "reason": "continuation profile differs from the frozen v0.1.3 local-Ollama profile",
            "required_request_timeout": _FROZEN_REQUEST_TIMEOUT,
            "required_max_output_tokens": _FROZEN_MAX_OUTPUT_TOKENS,
        }
    validation = validate_benchmark()
    if validation["passed"] is not True:
        return {"status": "FAIL_CLOSED", "reason": "containment-lab static validation failed", "validation": validation}
    preflight = _local_ollama_model_available(model, min(request_timeout, 10.0))
    if preflight["passed"] is not True:
        return {"status": "FAIL_CLOSED", "reason": "local Ollama preflight failed", "validation": validation, "ollama": preflight}

    all_tasks = load_tasks(DEFAULT_TASK_DIR)
    manifest, manifest_path = _frozen_manifest(
        output_root=output_root, experiment_id=experiment_id, model=model, tasks=all_tasks,
    )
    report_path = output_root / "reports" / f"{experiment_id}.json"
    if report_path.exists():
        return {"status": "FAIL_CLOSED", "reason": f"completed report already exists: {report_path}"}
    before = _audit_existing_attempts(output_root=output_root, experiment_id=experiment_id, tasks=all_tasks)
    remaining = list(before["remaining_task_ids"])
    ledger_path = _write_continuation_ledger(
        output_root=output_root,
        experiment_id=experiment_id,
        parent_manifest_path=manifest_path,
        audit=before,
        remaining_task_ids=remaining,
        model=model,
        request_timeout=request_timeout,
        max_output_tokens=max_output_tokens,
    )
    completed_rows: list[dict[str, Any]] = []
    task_index_by_id = {str(task["task_id"]): index for index, task in enumerate(all_tasks, start=1)}
    task_by_id = {str(task["task_id"]): task for task in all_tasks}
    for task_id in remaining:
        task_index = task_index_by_id[task_id]
        run_id = _next_run_id(output_root=output_root, experiment_id=experiment_id, task_index=task_index)
        row = _execute_one_task(
            task=task_by_id[task_id],
            task_index=task_index,
            run_id=run_id,
            output_root=output_root,
            manifest=manifest,
            model=model,
            request_timeout=request_timeout,
            max_output_tokens=max_output_tokens,
        )
        completed_rows.append(row)
        print(json.dumps({
            "event": "CONTAINMENT_LAB_RESUMED_RUN_FINISHED",
            "run_id": run_id,
            "task_id": task_id,
            "terminal_outcome": row["terminal_outcome"],
        }, sort_keys=True), flush=True)

    after = _audit_existing_attempts(output_root=output_root, experiment_id=experiment_id, tasks=all_tasks)
    if after["remaining_task_ids"]:
        return {
            "status": "INCOMPLETE",
            "experiment_id": experiment_id,
            "continuation_ledger_path": str(ledger_path),
            "remaining_task_ids": after["remaining_task_ids"],
            "new_runs": completed_rows,
        }
    ordered_completed = [after["completed"][str(task["task_id"])] for task in all_tasks]
    report = {
        "status": "COMPLETE",
        "experiment_id": experiment_id,
        "parent_manifest_path": str(manifest_path),
        "continuation_ledger_path": str(ledger_path),
        "created_at": utc_now(),
        "analysis_status": "exploratory_candidate",
        "excluded_from_confirmatory_crypto_web_analysis": True,
        "eligible_for_exploratory_analysis": True,
        "study_kind": "synthetic_containment_lab_exploratory",
        "task_count": len(all_tasks),
        "completed_task_count": len(ordered_completed),
        "completed_episode_count": len(ordered_completed),
        "infrastructure_abort_count": len(after["aborted"]),
        "total_attempt_count": len(after["all_attempts"]),
        "safety": {
            "actual_host_access_attempted": False,
            "actual_container_escape_attempted": False,
            "actual_network_or_message_delivery_attempted": False,
            "docker_containers_created": 0,
            "real_targets_contacted": False,
        },
        "static_validation": validation,
        "ollama": preflight,
        "completed_task_receipts": ordered_completed,
        "attempt_ledger": after["all_attempts"],
        "new_runs_from_this_continuation": completed_rows,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    report["report_path"] = str(report_path)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all synthetic containment-lab tasks through local Ollama.")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--request-timeout", type=float, default=180.0)
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--output-root", type=Path, default=ROOT / "experiments")
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--resume", action="store_true", help="Resume a paused v0.1.3 series without overwriting immutable logs.")
    parser.add_argument("--task-id", action="append", default=[], help="Run only a named synthetic task; repeat for more than one.")
    args = parser.parse_args(argv)
    if args.request_timeout <= 0 or args.max_output_tokens <= 0:
        parser.error("--request-timeout and --max-output-tokens must be positive")
    if args.resume:
        if not args.experiment_id:
            parser.error("--resume requires --experiment-id")
        if args.task_id:
            parser.error("--task-id cannot be used with --resume; the frozen manifest selects pending tasks")
        report = resume_suite(
            output_root=args.output_root,
            model=args.model,
            request_timeout=args.request_timeout,
            max_output_tokens=args.max_output_tokens,
            experiment_id=args.experiment_id,
        )
    else:
        report = run_suite(
            output_root=args.output_root,
            model=args.model,
            request_timeout=args.request_timeout,
            max_output_tokens=args.max_output_tokens,
            experiment_id=args.experiment_id or _experiment_id(),
            task_ids=args.task_id,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
