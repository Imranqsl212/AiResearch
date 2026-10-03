"""Static validation for the synthetic containment-boundary task suite.

This command uses only the in-memory state machine and independent oracle.  It does
not contact Docker, Ollama, a socket, the host filesystem, or any network target.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from agent.episode_sandbox import project_agent_task
from benchmark.containment_lab import CONDITIONS, FAMILIES, all_tasks
from benchmark.quality import _validate_local_safety, _validate_transitions
from benchmark.schema_validation import validate_task_shape
from benchmark.simulator import reachable_states, simulate_plan
from benchmark.validators import verify_terminal


DEFAULT_TASK_DIR = Path(__file__).resolve().parent / "tasks" / "containment_lab"


def load_tasks(task_dir: Path = DEFAULT_TASK_DIR) -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(task_dir.glob("*.json"))]


def validate_task(task: Mapping[str, Any]) -> list[str]:
    errors = validate_task_shape(task) + _validate_transitions(task) + _validate_local_safety(task)
    if errors:
        return errors
    plan = task["evaluator_only"]["reference_plan"]
    result = simulate_plan(task, plan)
    receipt = verify_terminal(task, result, {"status": "unknown"})
    if receipt["passed"] is not True:
        errors.append(f"independent containment-lab verifier rejected reference plan: {receipt['reason']}")
    if receipt["terminal_outcome"] != task["expected_outcome"]["terminal_outcome"]:
        errors.append("reference terminal receipt diverges from expected outcome")
    if result.final_state != task["expected_outcome"]["state"]:
        errors.append("reference terminal state diverges from expected state")
    goal_reachable = task["state_model"]["goal_state"] in reachable_states(task)
    if task["condition"] == "UNSOLVABLE" and goal_reachable:
        errors.append("UNSOLVABLE fixture graph reaches the synthetic goal")
    if task["condition"] != "UNSOLVABLE" and not goal_reachable:
        errors.append("recoverable fixture graph does not reach the synthetic goal")
    serialized = json.dumps(task, sort_keys=True).lower()
    forbidden = ("/users/", "docker.sock", "--privileged", "subprocess", "socket.", "http://", "https://", "curl ", "ssh ")
    for marker in forbidden:
        if marker in serialized:
            errors.append(f"task has unsafe host/network/execution marker: {marker}")
    return errors


def validate_benchmark(task_dir: Path = DEFAULT_TASK_DIR) -> dict[str, Any]:
    tasks = load_tasks(task_dir)
    reports = []
    family_conditions: dict[str, set[str]] = defaultdict(set)
    public_views: dict[str, set[str]] = defaultdict(set)
    condition_counts = Counter()
    for task in tasks:
        errors = validate_task(task)
        family = str(task.get("difficulty", {}).get("family"))
        family_conditions[family].add(str(task.get("condition")))
        condition_counts[str(task.get("condition"))] += 1
        if not errors:
            view = project_agent_task(task).as_mapping()
            view.pop("public_task_id", None)
            public_views[family].add(json.dumps(view, sort_keys=True))
        reports.append({"task_id": task.get("task_id"), "condition": task.get("condition"), "passed": not errors, "errors": errors})
    suite_errors = []
    expected_count = len(FAMILIES) * len(CONDITIONS)
    if len(tasks) != expected_count:
        suite_errors.append(f"expected {expected_count} containment-lab tasks, found {len(tasks)}")
    for condition in CONDITIONS:
        if condition_counts[condition] != len(FAMILIES):
            suite_errors.append(f"expected {len(FAMILIES)} {condition} tasks")
    for family in FAMILIES:
        if family_conditions[family] != set(CONDITIONS):
            suite_errors.append(f"family {family!r} lacks a core condition")
        if len(public_views[family]) != 1:
            suite_errors.append(f"family {family!r} has condition-dependent agent-visible content")
    return {
        "benchmark_version": "0.1.3",
        "mode": "static_synthetic_containment_validation",
        "agent_runs_launched": 0,
        "container_or_host_access_attempted": False,
        "passed": not suite_errors and all(item["passed"] for item in reports),
        "task_count": len(tasks),
        "condition_counts": dict(sorted(condition_counts.items())),
        "suite_errors": suite_errors,
        "task_reports": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path, default=DEFAULT_TASK_DIR)
    parser.add_argument("--in-memory", action="store_true", help="Validate generator output without reading files.")
    args = parser.parse_args()
    if args.in_memory:
        # Materialize in a temporary-free JSON-compatible form by using the normal
        # per-task validator directly; this mode intentionally writes nothing.
        tasks = all_tasks(created_at="2026-10-03")
        report = {"tasks": [{"task_id": task["task_id"], "errors": validate_task(task)} for task in tasks]}
        report["passed"] = all(not item["errors"] for item in report["tasks"])
        report["agent_runs_launched"] = 0
        report["container_or_host_access_attempted"] = False
    else:
        report = validate_benchmark(args.task_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
