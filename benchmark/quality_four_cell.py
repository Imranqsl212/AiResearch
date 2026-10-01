"""Static quality checks for the matched RD/UD/RW/UW development suite.

This command does not launch Docker, an agent, or a network connection.  It checks
public parity and deterministic declarative reference paths.  Executable-target
reachability remains a separate gate and cannot be inferred from these checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent.episode_sandbox import project_agent_task
from benchmark.four_cell import BENCHMARK_VERSION, FOUR_CELL_CONDITIONS
from benchmark.simulator import reachable_states, simulate_plan
from benchmark.validators.four_cell import verify_four_cell_receipt
from benchmark.validators.four_cell_oracles import oracle_for


DEFAULT_TASK_DIR = Path(__file__).resolve().parent / "tasks" / "four_cell"


def load_tasks(task_dir: Path = DEFAULT_TASK_DIR) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for path in sorted(task_dir.glob("*.json")):
        tasks.append(json.loads(path.read_text(encoding="utf-8")))
    return tasks


def _public_hash(task: Mapping[str, Any]) -> str:
    public = project_agent_task(task).as_mapping()
    public.pop("public_task_id", None)
    return hashlib.sha256(json.dumps(public, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate_task(task: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ("schema_version", "task_id", "condition", "difficulty", "state_model", "evaluator_only", "verifier")
    missing = [field for field in required if field not in task]
    if missing:
        return [f"missing required fields: {', '.join(missing)}"]
    if task["schema_version"] != "0.3.0":
        errors.append("schema_version must equal 0.3.0")
    if task["condition"] not in FOUR_CELL_CONDITIONS:
        errors.append("condition is not one of RD/UD/RW/UW")
    model = task["state_model"]
    transitions = model.get("transitions", [])
    if not isinstance(transitions, list) or not transitions:
        errors.append("state_model.transitions must be a non-empty list")
    elif task["difficulty"].get("transition_count") != len(transitions):
        errors.append("difficulty.transition_count does not match transition count")
    if task["verifier"].get("id") != "crypto_four_cell_receipt_v1":
        errors.append("unexpected verifier id")
    oracle = oracle_for(task)
    if oracle is None:
        errors.append("no independent oracle is registered for this family/condition")
    if not isinstance(task.get("evaluator_only", {}).get("reference_plan"), list):
        errors.append("evaluator_only.reference_plan must be a list")
    else:
        result = simulate_plan(task, task["evaluator_only"]["reference_plan"])
        if result.final_state != oracle["expected_state"]:
            errors.append("reference plan does not reach the independent oracle terminal state")
        if task["condition"] in {"UD", "UW"} and task["state_model"]["goal_state"] in reachable_states(task):
            errors.append("unavailable condition has a graph path to goal_state")
        if task["condition"] in {"RD", "RW"} and task["state_model"]["goal_state"] not in reachable_states(task):
            errors.append("recoverable condition has no graph path to goal_state")
        receipt = {
            "task_id": task["task_id"],
            "task_version": task["version"],
            "verifier_version": "0.3.0",
            "terminal_state": result.final_state,
            "evidence_classes": sorted({event["observation"]["evidence_class"] for event in result.events}),
            "state_hash": hashlib.sha256(result.final_state.encode()).hexdigest(),
            "channel": "evaluator_only",
        }
        verification = verify_four_cell_receipt(task, receipt, agent_claim={"status": "success" if oracle["goal_reachable"] else "unavailable"})
        if not verification["passed"]:
            errors.append(f"independent receipt validation failed: {verification['reason']}")
    return errors


def validate_benchmark(task_dir: Path = DEFAULT_TASK_DIR) -> dict[str, Any]:
    tasks = load_tasks(task_dir)
    reports: list[dict[str, Any]] = []
    families: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for task in tasks:
        family = str(task.get("difficulty", {}).get("family", "<missing>"))
        families[family].append(task)
        errors = _validate_task(task)
        reports.append({"task_id": task.get("task_id"), "family": family, "condition": task.get("condition"), "passed": not errors, "errors": errors})

    suite_errors: list[str] = []
    if not tasks:
        suite_errors.append("no four-cell task manifests found")
    for family, members in sorted(families.items()):
        conditions = [str(task.get("condition")) for task in members]
        if sorted(conditions) != sorted(FOUR_CELL_CONDITIONS):
            suite_errors.append(f"family {family!r} must contain exactly one RD, UD, RW, and UW")
        if len({_public_hash(task) for task in members}) != 1:
            suite_errors.append(f"family {family!r} has condition-dependent public projection")
        if len({task.get("difficulty", {}).get("transition_count") for task in members}) != 1:
            suite_errors.append(f"family {family!r} has unmatched transition counts")
        if len({json.dumps(task.get("tool_contract"), sort_keys=True) for task in members}) != 1:
            suite_errors.append(f"family {family!r} has unmatched tool contracts")

    counts = Counter(task.get("condition") for task in tasks)
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "mode": "static_four_cell_validation",
        "agent_runs_launched": 0,
        "passed": not suite_errors and all(report["passed"] for report in reports),
        "task_count": len(tasks),
        "family_count": len(families),
        "condition_counts": dict(sorted(counts.items())),
        "suite_errors": suite_errors,
        "tasks": reports,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate matched four-cell tasks without launching an agent.")
    parser.add_argument("--task-dir", type=Path, default=DEFAULT_TASK_DIR)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate_benchmark(args.task_dir)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"{'PASS' if report['passed'] else 'FAIL'}: {report['task_count']} tasks")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
