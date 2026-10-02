"""Resumable Docker-backed pilot/main runner for the frozen executable catalog.

This module is intentionally a runner, not an analysis script.  It freezes a
schedule and manifest, reserves every slot before handing a task to Ollama, and
binds a completed raw log/receipt pair to the attempt ledger.  The model sees
only the public task projection; condition, expected outcome, and verifier state
remain evaluator-side.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

from agent.episode_sandbox import opaque_public_task_id
from agent.ollama_adapter import OllamaAdapter
from agent.runner import EpisodeRunner, opaque_public_run_id
from agent.contracts import RunContext
from benchmark.executable_catalog import EXECUTABLE_BENCHMARK_VERSION
from experiments.attempt_ledger import AttemptLedgerError, AttemptLedgerWriter
from experiments.executable_episode import (
    ExecutableCatalogSandbox,
    verify_executable_action,
    verify_executable_terminal,
)
from experiments.manifest import ExperimentManifest, resolve_git_commit, utc_now, write_manifest
from experiments.raw_archive import archive_run, seal_archive
from experiments.schedule import build_schedule, validate_schedule, write_schedule
from experiments.trajectory_logger import TrajectoryLogger


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "benchmark" / "tasks" / "executable" / "catalog.jsonl"
AGENT_VERSION = "ollama-local-adapter-0.2.0"
VERIFIER_VERSION = "0.4.0"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_MAX_STEPS = 8
DEFAULT_SEED = 7


def load_catalog(path: Path = CATALOG_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"catalog line {line_number} is not an object")
        rows.append(row)
    if len(rows) != 80:
        raise ValueError(f"expected 80 executable tasks, found {len(rows)}")
    versions = {row.get("version") for row in rows}
    if versions != {EXECUTABLE_BENCHMARK_VERSION}:
        raise ValueError(f"catalog versions are not frozen at {EXECUTABLE_BENCHMARK_VERSION}: {versions}")
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _experiment_id(
    phase: str, benchmark_version: str, prefix: str = "executable"
) -> str:
    return f"{prefix}-{phase}-{benchmark_version.replace('.', '-') }"


def select_tasks(rows: Sequence[dict[str, Any]], phase: str, pilot_families: Sequence[str]) -> list[dict[str, Any]]:
    if phase == "main":
        selected = list(rows)
    else:
        wanted = set(pilot_families)
        if not wanted:
            raise ValueError("pilot requires at least one family")
        selected = [row for row in rows if row.get("family") in wanted]
    if not selected:
        raise ValueError("task selection is empty")
    by_family: dict[str, set[str]] = {}
    for row in selected:
        by_family.setdefault(str(row["family"]), set()).add(str(row["condition"]))
    expected = {"RD", "UD", "RW", "UW"}
    incomplete = {family: sorted(conditions) for family, conditions in by_family.items() if conditions != expected}
    if incomplete:
        raise ValueError(f"selected families are not complete four-cell blocks: {incomplete}")
    return sorted(selected, key=lambda row: str(row["task_id"]))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if _load_json(path) != value:
            raise RuntimeError(f"refusing to overwrite frozen JSON: {path}")
        return
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def prepare_study(
    *, phase: str, model: str, runs_per_task: int, timeout_seconds: int,
    max_steps: int, pilot_families: Sequence[str], output_root: Path,
    request_timeout: float = 300.0,
    task_rows: Sequence[dict[str, Any]] | None = None,
    experiment_prefix: str = "executable",
) -> tuple[Path, Path, ExperimentManifest, list[dict[str, Any]]]:
    rows = (
        list(task_rows)
        if task_rows is not None
        else select_tasks(load_catalog(), phase, pilot_families)
    )
    if not rows:
        raise ValueError("study requires at least one task row")
    if request_timeout <= 0:
        raise ValueError("request_timeout must be positive")
    experiment_id = _experiment_id(
        phase, EXECUTABLE_BENCHMARK_VERSION, experiment_prefix
    )
    schedules = output_root / "schedules"
    manifests = output_root / "manifests"
    schedule_path = schedules / f"{experiment_id}.json"
    manifest_path = manifests / f"{experiment_id}.json"

    if schedule_path.exists() != manifest_path.exists():
        raise RuntimeError("frozen schedule and manifest must either both exist or both be absent")

    git_commit = resolve_git_commit(ROOT)
    if schedule_path.exists():
        schedule = _load_json(schedule_path)
        manifest_document = _load_json(manifest_path)
        validate_schedule(schedule, manifest=manifest_document, tasks=rows)
        immutable_expected = {
            "model": model,
            "runs_per_task": runs_per_task,
            "max_steps": max_steps,
            "timeout_seconds": timeout_seconds,
        }
        mismatches = {key: (manifest_document.get(key), value) for key, value in immutable_expected.items() if manifest_document.get(key) != value}
        frozen_notes = str(manifest_document.get("notes", ""))
        timeout_marker = f"provider_request_timeout_seconds={request_timeout:g}"
        note_fields = {part.strip() for part in frozen_notes.split(";")}
        if any(part.startswith("provider_request_timeout_seconds=") for part in note_fields) and timeout_marker not in note_fields:
            mismatches["provider_request_timeout_seconds"] = (frozen_notes, request_timeout)
        if mismatches:
            raise RuntimeError(f"existing frozen study configuration differs: {mismatches}")
        manifest = ExperimentManifest(
            experiment_id=experiment_id, model=str(manifest_document["model"]),
            agent_version=str(manifest_document["agent_version"]), benchmark_version=str(manifest_document["benchmark_version"]),
            task_ids=tuple(str(item) for item in manifest_document["task_ids"]), runs_per_task=int(manifest_document["runs_per_task"]),
            temperature=manifest_document.get("temperature"), max_steps=int(manifest_document["max_steps"]), timeout_seconds=int(manifest_document["timeout_seconds"]),
            git_commit=str(manifest_document["git_commit"]), adapter_type=str(manifest_document["adapter_type"]),
            sandbox_type=str(manifest_document["sandbox_type"]), safety_mode=str(manifest_document["safety_mode"]),
            seed=manifest_document.get("seed"), token_budget=manifest_document.get("token_budget"),
            schedule_sha256=str(manifest_document["schedule_sha256"]), notes=str(manifest_document.get("notes", "")),
            created_at=str(manifest_document.get("created_at", "")), date=str(manifest_document.get("date", "")),
        )
        return manifest_path, schedule_path, manifest, rows

    schedule = build_schedule(
        experiment_id=experiment_id, tasks=rows, runs_per_task=runs_per_task, seed=DEFAULT_SEED
    )
    write_schedule(schedule, schedule_path)
    schedule_hash = _sha256(schedule_path)
    manifest = ExperimentManifest(
        experiment_id=experiment_id, model=model, agent_version=AGENT_VERSION,
        benchmark_version=EXECUTABLE_BENCHMARK_VERSION,
        task_ids=tuple(str(row["task_id"]) for row in rows), runs_per_task=runs_per_task,
        temperature=0, max_steps=max_steps, timeout_seconds=timeout_seconds,
        git_commit=git_commit, adapter_type="ollama_local_loopback",
        sandbox_type="docker_candidate_runtime", safety_mode="local_no_external_target_fail_closed",
        seed=DEFAULT_SEED, token_budget=None, schedule_sha256=schedule_hash,
        notes=(f"{phase} study; evaluator-owned Docker target; {len(rows)} tasks; "
               f"provider_request_timeout_seconds={request_timeout:g}; "
               "raw trajectories and receipts are excluded from Git and must be archived separately."),
    )
    write_manifest(manifest, manifests)
    return manifest_path, schedule_path, manifest, rows


def _load_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        slot_id = row.get("slot_id")
        if not isinstance(slot_id, str) or slot_id in result:
            raise RuntimeError(f"duplicate or invalid result slot at line {line_number}")
        result[slot_id] = row
    return result


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _completed_run(ledger: AttemptLedgerWriter, slot_id: str) -> str | None:
    directory = ledger.journal_dir / slot_id
    if not directory.is_dir():
        return None
    completed = sorted(directory.glob("attempt-*.completed.json"))
    if not completed:
        return None
    document = _load_json(completed[-1])
    return str(document["run_id"]) if document.get("classification") == "SELECTED" else None


def _run_one(
    *, task: dict[str, Any], slot: dict[str, Any], manifest: ExperimentManifest,
    output_root: Path, model: str, request_timeout: float,
) -> dict[str, Any]:
    run_id = f"{manifest.experiment_id}-{slot['slot_id']}"
    context = RunContext(
        experiment_id=manifest.experiment_id, run_id=run_id, model=manifest.model,
        agent_version=manifest.agent_version, benchmark_version=manifest.benchmark_version,
        git_commit=manifest.git_commit, started_at=utc_now(), max_steps=manifest.max_steps,
        timeout_seconds=manifest.timeout_seconds, seed=manifest.seed, temperature=manifest.temperature,
        token_budget=manifest.token_budget,
    )
    public_task_id = opaque_public_task_id(str(task["task_id"]), str(task["version"]))
    public_run_id = opaque_public_run_id(context)
    logger = TrajectoryLogger(
        output_root / "runs", context, task_id=str(task["task_id"]), condition=str(task["condition"]),
        public_task_id=public_task_id, public_run_id=public_run_id,
    )
    adapter = OllamaAdapter(model=model, request_timeout=request_timeout)
    sandbox = ExecutableCatalogSandbox(task)
    result = EpisodeRunner(
        adapter=adapter, sandbox=sandbox, logger=logger, context=context,
        public_task_id=public_task_id, public_run_id=public_run_id,
        terminal_verifier=verify_executable_terminal, action_verifier=verify_executable_action,
    ).run(task)
    mapping = result.as_mapping()
    mapping.update({
        "slot_id": slot["slot_id"], "order": slot["order"], "repeat_index": slot["repeat_index"],
        "task_family": task["family"], "domain": task["domain"], "task_condition": task["condition"],
        "verifier_version": VERIFIER_VERSION,
        "task_state": (result.verifier_receipt or {}).get("task_state") if result.verifier_receipt else None,
        "expected_task_state": (result.verifier_receipt or {}).get("expected_task_state") if result.verifier_receipt else None,
        "claim_supported": (result.verifier_receipt or {}).get("claim_supported") if result.verifier_receipt else None,
        "base_task_id": task.get("base_task_id", task["task_id"]),
        "retrieval_mode": task.get("retrieval_mode", "not_applicable"),
        "retrieval_context_sha256": (
            task.get("retrieval_context", {}).get("corpus_sha256")
            if isinstance(task.get("retrieval_context"), dict)
            else None
        ),
    })
    return mapping


def run_study(
    *, phase: str, model: str, runs_per_task: int, request_timeout: float,
    timeout_seconds: int, max_steps: int, pilot_families: Sequence[str],
    output_root: Path,
    task_rows: Sequence[dict[str, Any]] | None = None,
    experiment_prefix: str = "executable",
    fail_on_infrastructure_abort: bool = False,
) -> dict[str, Any]:
    expected_output_root = (ROOT / "experiments").resolve()
    if output_root.resolve() != expected_output_root:
        raise ValueError(
            f"output_root must remain the repository experiment root for attempt-ledger integrity: {expected_output_root}"
        )
    manifest_path, schedule_path, manifest, tasks = prepare_study(
        phase=phase, model=model, runs_per_task=runs_per_task,
        timeout_seconds=timeout_seconds, max_steps=max_steps,
        request_timeout=request_timeout,
        pilot_families=pilot_families, output_root=output_root,
        task_rows=task_rows, experiment_prefix=experiment_prefix,
    )
    schedule = _load_json(schedule_path)
    task_by_id = {str(row["task_id"]): row for row in tasks}
    ledger = AttemptLedgerWriter(root=ROOT, manifest_path=manifest_path, schedule_path=schedule_path, tasks=tasks)
    results_path = output_root / "results" / f"{manifest.experiment_id}.jsonl"
    existing = _load_results(results_path)
    archive_root = output_root / "raw_archive" / manifest.experiment_id
    completed = 0
    skipped = 0
    for slot in schedule["slots"]:
        slot_id = str(slot["slot_id"])
        if _completed_run(ledger, slot_id) is not None:
            skipped += 1
            continue
        task = task_by_id.get(str(slot["task_id"]))
        if task is None:
            raise RuntimeError(f"scheduled task is absent from selected catalog: {slot['task_id']}")
        run_id = f"{manifest.experiment_id}-{slot_id}"
        if slot_id in existing:
            raise RuntimeError(f"result exists but ledger is not completed for {slot_id}; refusing to guess recovery state")
        ledger.reserve(slot_id=slot_id, run_id=run_id)
        print(json.dumps({"event": "START", "phase": phase, "slot_id": slot_id, "task_id": task["task_id"], "condition": task["condition"], "family": task["family"]}, sort_keys=True), flush=True)
        mapping = _run_one(
            task=task, slot=slot, manifest=manifest, output_root=output_root,
            model=model, request_timeout=request_timeout,
        )
        ledger.complete(slot_id=slot_id, run_id=run_id)
        _append_jsonl(results_path, mapping)
        archive_run(Path(mapping["log_path"]), archive_root, run_id)
        completed += 1
        print(json.dumps({"event": "FINISH", "slot_id": slot_id, "run_id": run_id, "terminal_outcome": mapping["terminal_outcome"], "verifier_terminal_outcome": mapping["verifier_terminal_outcome"], "task_state": mapping["task_state"], "stop_event": mapping["stop_event"], "steps": mapping["steps_executed"]}, sort_keys=True), flush=True)
        if fail_on_infrastructure_abort and mapping["terminal_outcome"] == "INFRASTRUCTURE_ABORT":
            raise RuntimeError(f"infrastructure abort in {slot_id}; run preserved; further slots halted")
    ledger_path = ledger.finalize()
    archive_manifest = seal_archive(archive_root, experiment_id=manifest.experiment_id, manifest_version=manifest.schema_version)
    report = {
        "phase": phase, "experiment_id": manifest.experiment_id,
        "manifest": str(manifest_path), "schedule": str(schedule_path),
        "ledger": str(ledger_path), "results": str(results_path),
        "archive_manifest": str(archive_manifest), "scheduled_slots": len(schedule["slots"]),
        "completed_this_invocation": completed, "skipped_completed": skipped,
        "main_experiment_started": phase == "main", "raw_data_mutated": False,
    }
    report_path = output_root / "reports" / f"{manifest.experiment_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run/resume the Docker-backed executable crypto/web study.")
    parser.add_argument("--phase", choices=("pilot", "main"), required=True)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--runs-per-task", type=int, default=None)
    parser.add_argument("--request-timeout", type=float, default=300.0)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--pilot-families", nargs="+", default=["aead", "key-derivation", "sqli"])
    parser.add_argument("--output-root", type=Path, default=ROOT / "experiments")
    args = parser.parse_args(argv)
    repeats = args.runs_per_task if args.runs_per_task is not None else (1 if args.phase == "pilot" else 3)
    if repeats <= 0 or args.request_timeout <= 0 or args.timeout_seconds <= 0 or args.max_steps <= 0:
        parser.error("run counts, timeouts, and max-steps must be positive")
    try:
        report = run_study(
            phase=args.phase, model=args.model, runs_per_task=repeats,
            request_timeout=args.request_timeout, timeout_seconds=args.timeout_seconds,
            max_steps=args.max_steps, pilot_families=args.pilot_families,
            output_root=args.output_root,
        )
    except (AttemptLedgerError, RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
