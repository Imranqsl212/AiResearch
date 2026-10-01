"""Dependency-free integrity checks for frozen manifests, JSONL logs, and receipts.

The validator is intentionally observational: it does not rerun an agent or a task,
and it never treats a task-level non-success as a logging defect.  It checks whether an
already collected evaluator-owned record is complete, internally consistent, and tied
to its immutable receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.contracts import ObservableDataError, assert_observable_payload
from experiments.manifest import MANIFEST_SCHEMA_VERSION, UNAVAILABLE_GIT_COMMIT
from experiments.trajectory_logger import TRAJECTORY_LOG_SCHEMA_VERSION


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EVENT_SCHEMA_PATH = REPOSITORY_ROOT / "experiments" / "schemas" / "trajectory_event.schema.json"
MANIFEST_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "experiment_id",
        "model",
        "agent_version",
        "benchmark_version",
        "task_ids",
        "task_count",
        "runs_per_task",
        "temperature",
        "max_steps",
        "timeout_seconds",
        "git_commit",
        "adapter_type",
        "sandbox_type",
        "safety_mode",
        "seed",
        "token_budget",
        "notes",
        "created_at",
        "date",
    }
)
RECEIPT_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "experiment_id",
        "run_id",
        "public_run_id",
        "task_id",
        "public_task_id",
        "condition",
        "model",
        "agent_version",
        "benchmark_version",
        "git_commit",
        "log_file",
        "log_sha256",
        "terminal_outcome",
        "stop_event",
        "verifier_receipt",
        "errors",
        "finalized_at",
    }
)


def _read_json(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        errors.append(f"{label} is missing: {path}")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    return value


def _expected_event_fields(errors: list[str]) -> set[str]:
    schema = _read_json(EVENT_SCHEMA_PATH, "trajectory event schema", errors)
    if schema is None:
        return set()
    required = schema.get("required")
    if not isinstance(required, list) or not all(isinstance(field, str) for field in required):
        errors.append("trajectory event schema does not declare a string required list")
        return set()
    return set(required)


def _validate_manifest(
    document: Mapping[str, Any], *, require_git: bool, errors: list[str], warnings: list[str]
) -> None:
    missing = sorted(MANIFEST_REQUIRED_FIELDS - set(document))
    if missing:
        errors.append(f"manifest is missing required fields: {', '.join(missing)}")
    if document.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append("manifest schema_version does not match the supported contract")
    task_ids = document.get("task_ids")
    if not isinstance(task_ids, list) or not task_ids or not all(isinstance(item, str) and item for item in task_ids):
        errors.append("manifest task_ids must be a non-empty string list")
    elif document.get("task_count") != len(task_ids):
        errors.append("manifest task_count does not match task_ids")
    for field in ("runs_per_task", "max_steps", "timeout_seconds"):
        value = document.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            errors.append(f"manifest {field} must be a positive integer")
    git_commit = document.get("git_commit")
    if not isinstance(git_commit, str) or not git_commit:
        errors.append("manifest git_commit must be a non-empty string")
    elif git_commit == UNAVAILABLE_GIT_COMMIT:
        message = "Git revision is unavailable; the manifest cannot identify an immutable source tree"
        (errors if require_git else warnings).append(message)
    elif require_git and re.fullmatch(r"[0-9a-f]{40,64}", git_commit) is None:
        errors.append("main-study Git revision must be a full lowercase commit SHA")
    schedule_sha256 = document.get("schedule_sha256")
    if schedule_sha256 is not None and (
        not isinstance(schedule_sha256, str)
        or len(schedule_sha256) != 64
        or any(character not in "0123456789abcdef" for character in schedule_sha256)
    ):
        errors.append("manifest schedule_sha256 must be a SHA-256 hex digest")
    try:
        assert_observable_payload(document, "manifest")
    except ObservableDataError as exc:
        errors.append(f"manifest violates observable-data policy: {exc}")


def validate_manifest(path: Path, *, require_git: bool = False) -> dict[str, Any]:
    """Validate a manifest even when no run or receipt exists yet."""

    errors: list[str] = []
    warnings: list[str] = []
    document = _read_json(path, "manifest", errors)
    if document is not None:
        _validate_manifest(document, require_git=require_git, errors=errors, warnings=warnings)
    return {"passed": not errors, "errors": errors, "warnings": warnings}


def _read_log(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        errors.append(f"trajectory log is missing: {path}")
        return records
    if not lines:
        errors.append("trajectory log is empty")
        return records
    for line_number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"trajectory log line {line_number} is invalid JSON: {exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"trajectory log line {line_number} is not an object")
            continue
        records.append(record)
    return records


def _validate_log(
    records: Sequence[Mapping[str, Any]],
    *,
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    require_action_verifier: bool,
    errors: list[str],
) -> None:
    required_fields = _expected_event_fields(errors)
    if not records:
        return
    expected_identity = {
        "experiment_id": receipt.get("experiment_id"),
        "run_id": receipt.get("run_id"),
        "public_run_id": receipt.get("public_run_id"),
        "task_id": receipt.get("task_id"),
        "public_task_id": receipt.get("public_task_id"),
        "condition": receipt.get("condition"),
        "model": receipt.get("model"),
        "agent_version": receipt.get("agent_version"),
        "benchmark_version": receipt.get("benchmark_version"),
        "git_commit": receipt.get("git_commit"),
    }
    event_ids: list[str] = []
    event_types: list[str] = []
    action_index = 0
    for index, record in enumerate(records, start=1):
        missing = sorted(required_fields - set(record))
        if missing:
            errors.append(f"trajectory event {index} is missing fields: {', '.join(missing)}")
        if record.get("schema_version") != TRAJECTORY_LOG_SCHEMA_VERSION:
            errors.append(f"trajectory event {index} has an unsupported schema version")
        for field, expected in expected_identity.items():
            if expected is not None and record.get(field) != expected:
                errors.append(f"trajectory event {index} disagrees with receipt on {field}")
        try:
            assert_observable_payload(record, f"trajectory event {index}")
        except ObservableDataError as exc:
            errors.append(f"trajectory event {index} violates observable-data policy: {exc}")
        event_id = record.get("event_id")
        if isinstance(event_id, str):
            event_ids.append(event_id)
        event_type = record.get("event_type")
        if isinstance(event_type, str):
            event_types.append(event_type)
        if event_type == "TOOL_OBSERVATION":
            action_index += 1
            action_verifier = record.get("verifier_result")
            if (require_action_verifier and action_verifier is None
                    and receipt.get("terminal_outcome") != "INFRASTRUCTURE_ABORT"):
                errors.append(f"trajectory event {index} lacks required per-action evaluator verifier receipt")
            if action_verifier is not None and (
                not isinstance(action_verifier, Mapping)
                or action_verifier.get("source") != "evaluator_action_verifier"
                or type(action_verifier.get("action_index")) is not int
                or action_verifier["action_index"] != action_index
                or action_verifier.get("task_id") != receipt.get("task_id")
                or not isinstance(action_verifier.get("verifier_id"), str)
                or not action_verifier["verifier_id"]
                or not isinstance(action_verifier.get("verifier_version"), str)
                or not action_verifier["verifier_version"]
                or not isinstance(action_verifier.get("passed"), bool)
                or action_verifier.get("terminal_outcome") not in
                {"VALIDATED_SUCCESS", "VALIDATED_NON_SUCCESS", "UNKNOWN"}
                or (action_verifier.get("terminal_outcome") == "VALIDATED_SUCCESS"
                    and action_verifier.get("passed") is not True)
                or (action_verifier.get("terminal_outcome") == "UNKNOWN"
                    and action_verifier.get("passed") is not False)
            ):
                errors.append(f"trajectory event {index} has an invalid per-action evaluator verifier receipt")
    expected_event_ids = [f"event-{index:05d}" for index in range(1, len(records) + 1)]
    if event_ids != expected_event_ids:
        errors.append("trajectory event IDs are not a contiguous append-only sequence")
    handoff_positions = [index for index, kind in enumerate(event_types)
                         if kind == "TASK_HANDOFF_START"]
    if len(handoff_positions) > 1:
        errors.append("trajectory has duplicate task-handoff-start events")
    elif handoff_positions:
        exposure_kinds = {"INITIAL_OBSERVATION", "TOOL_CALL", "TOOL_OBSERVATION", "STOP"}
        if any(kind in exposure_kinds for kind in event_types[:handoff_positions[0]]):
            errors.append("task-handoff-start event must precede observation, tool use, and stop")
    steps = [record.get("step") for record in records]
    if any(not isinstance(step, int) or isinstance(step, bool) or step < 0 for step in steps):
        errors.append("trajectory steps must be non-negative integers")
    elif steps != sorted(steps):
        errors.append("trajectory steps are not monotone")
    if event_types[-1:] != ["RUN_FINISHED"]:
        errors.append("trajectory log must end with RUN_FINISHED")
    if event_types.count("RUN_FINISHED") != 1:
        errors.append("trajectory log must contain exactly one RUN_FINISHED event")
    infrastructure_abort = receipt.get("terminal_outcome") == "INFRASTRUCTURE_ABORT"
    if not infrastructure_abort:
        if event_types.count("STOP") != 1:
            errors.append("trajectory log must contain exactly one explicit STOP event")
        if event_types.count("VERIFIER_RECEIPT") != 1:
            errors.append("trajectory log must contain exactly one independent VERIFIER_RECEIPT event")
        if "STOP" in event_types and "VERIFIER_RECEIPT" in event_types and not (
            event_types.index("STOP") < event_types.index("VERIFIER_RECEIPT") < len(event_types) - 1
        ):
            errors.append("STOP, VERIFIER_RECEIPT, RUN_FINISHED event order is invalid")
    elif not any(kind in event_types for kind in ("ERROR", "CLEANUP_ERROR")):
        errors.append("infrastructure abort lacks an error event")
    final = records[-1]
    if final.get("outcome") != receipt.get("terminal_outcome"):
        errors.append("RUN_FINISHED outcome disagrees with receipt terminal_outcome")
    if final.get("stop_event") != receipt.get("stop_event"):
        errors.append("RUN_FINISHED stop_event disagrees with receipt")
    verifier_events = [record for record in records if record.get("event_type") == "VERIFIER_RECEIPT"]
    if verifier_events:
        event_verifier = verifier_events[-1].get("verifier_result")
        receipt_verifier = receipt.get("verifier_receipt")
        if event_verifier != receipt_verifier:
            errors.append("VERIFIER_RECEIPT event disagrees with final receipt")
        if not isinstance(receipt_verifier, Mapping):
            errors.append("independent verifier receipt is missing")
        elif (
            receipt_verifier.get("terminal_outcome") == "VALIDATED_SUCCESS"
            and receipt_verifier.get("passed") is not True
        ):
            errors.append("verifier marked success without passed=true")
        if isinstance(receipt_verifier, Mapping) and not infrastructure_abort and receipt.get("stop_event") == "AGENT_SELF_TERMINATION":
            if receipt.get("terminal_outcome") != receipt_verifier.get("terminal_outcome"):
                errors.append("voluntary terminal outcome disagrees with verifier receipt")
    if receipt.get("terminal_outcome") == "VALIDATED_SUCCESS":
        verifier = receipt.get("verifier_receipt")
        if not isinstance(verifier, Mapping) or verifier.get("passed") is not True or verifier.get("terminal_outcome") != "VALIDATED_SUCCESS":
            errors.append("validated success lacks a matching passing independent verifier")
    if receipt.get("task_id") not in manifest.get("task_ids", []):
        errors.append("receipt task_id is absent from the frozen manifest")
    if receipt.get("experiment_id") != manifest.get("experiment_id"):
        errors.append("receipt experiment_id does not match the manifest")
    if receipt.get("benchmark_version") != manifest.get("benchmark_version"):
        errors.append("receipt benchmark_version does not match the manifest")
    if receipt.get("model") != manifest.get("model"):
        errors.append("receipt model does not match the manifest")
    if receipt.get("agent_version") != manifest.get("agent_version"):
        errors.append("receipt agent_version does not match the manifest")
    if receipt.get("git_commit") != manifest.get("git_commit"):
        errors.append("receipt git_commit does not match the manifest")


def validate_artifacts(
    *,
    manifest_path: Path,
    log_path: Path,
    receipt_path: Path,
    require_git: bool = False,
    require_action_verifier: bool = False,
) -> dict[str, Any]:
    """Return a full integrity report without executing a task or agent."""

    errors: list[str] = []
    warnings: list[str] = []
    manifest = _read_json(manifest_path, "manifest", errors)
    receipt = _read_json(receipt_path, "receipt", errors)
    if manifest is not None:
        _validate_manifest(manifest, require_git=require_git, errors=errors, warnings=warnings)
    if receipt is not None:
        missing = sorted(RECEIPT_REQUIRED_FIELDS - set(receipt))
        if missing:
            errors.append(f"receipt is missing required fields: {', '.join(missing)}")
        if receipt.get("schema_version") != TRAJECTORY_LOG_SCHEMA_VERSION:
            errors.append("receipt schema_version does not match the supported contract")
        expected_digest = hashlib.sha256(log_path.read_bytes()).hexdigest() if log_path.is_file() else None
        if expected_digest is None:
            errors.append("cannot verify receipt digest because trajectory log is missing")
        elif receipt.get("log_sha256") != expected_digest:
            errors.append("receipt log_sha256 does not match the trajectory log bytes")
        if receipt.get("log_file") != log_path.name:
            errors.append("receipt log_file does not match the trajectory log path")
        try:
            assert_observable_payload(receipt, "receipt")
        except ObservableDataError as exc:
            errors.append(f"receipt violates observable-data policy: {exc}")
    records = _read_log(log_path, errors)
    if manifest is not None and receipt is not None:
        _validate_log(records, manifest=manifest, receipt=receipt,
                      require_action_verifier=require_action_verifier, errors=errors)
    return {
        "schema_version": "0.1.0",
        "kind": "observable_artifact_integrity_report",
        "manifest": str(manifest_path),
        "log": str(log_path),
        "receipt": str(receipt_path),
        "require_git": require_git,
        "require_action_verifier": require_action_verifier,
        "record_count": len(records),
        "terminal_outcome": receipt.get("terminal_outcome") if receipt else None,
        "verifier_passed": (
            receipt.get("verifier_receipt", {}).get("passed")
            if isinstance(receipt, Mapping) and isinstance(receipt.get("verifier_receipt"), Mapping)
            else None
        ),
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an existing manifest/log/receipt triplet.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--require-git",
        action="store_true",
        help="Treat an unavailable Git commit as an integrity error rather than a warning.",
    )
    parser.add_argument(
        "--require-action-verifier", action="store_true",
        help="Require an evaluator-owned receipt on every completed tool action except infrastructure aborts.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate_artifacts(
        manifest_path=args.manifest,
        log_path=args.log,
        receipt_path=args.receipt,
        require_git=args.require_git,
        require_action_verifier=args.require_action_verifier,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{'PASS' if report['passed'] else 'FAIL'}: {report['record_count']} records")
        for error in report["errors"]:
            print(f"  error: {error}")
        for warning in report["warnings"]:
            print(f"  warning: {warning}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
