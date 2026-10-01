"""Automated self-validation for the nine-task local pilot benchmark.

The command validates declarative task contracts and scripted reference paths only.
It never launches an AI agent, opens a network connection, executes a shell command,
or contacts an external target.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmark.schema_validation import TASK_CONDITIONS, validate_task_shape
from benchmark.simulator import reachable_states, simulate_plan
from benchmark.validators import verify_terminal
from agent.episode_sandbox import project_agent_task


DEFAULT_TASK_DIR = Path(__file__).resolve().parent / "tasks" / "pilot"


def load_tasks(task_dir: Path = DEFAULT_TASK_DIR) -> list[dict[str, Any]]:
    """Load only JSON manifests from a local benchmark directory."""

    tasks: list[dict[str, Any]] = []
    for path in sorted(task_dir.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            task = json.load(handle)
        tasks.append(task)
    return tasks


def _action_equals(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return left.get("tool") == right.get("tool") and left.get("parameters", {}) == right.get(
        "parameters", {}
    )


def _validate_transitions(task: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    model = task["state_model"]
    states = set(model["states"])
    tool_contract = task["tool_contract"]
    for required_state in ("initial_state", "goal_state", "stop_state"):
        if model[required_state] not in states:
            errors.append(f"state_model.{required_state} is absent from state_model.states")
    signatures: set[tuple[str, str, str]] = set()
    for index, transition in enumerate(model["transitions"]):
        prefix = f"state_model.transitions[{index}]"
        required = ("from", "tool", "parameters", "to", "observation", "outcome", "strategy", "adaptation")
        missing = [field for field in required if field not in transition]
        if missing:
            errors.append(f"{prefix} is missing {', '.join(missing)}")
            continue
        if transition["from"] not in states or transition["to"] not in states:
            errors.append(f"{prefix} references a state outside state_model.states")
        if transition["tool"] not in task["allowed_tools"]:
            errors.append(f"{prefix}.tool is not allowed by the task")
        if not isinstance(transition["parameters"], Mapping):
            errors.append(f"{prefix}.parameters must be an object")
        else:
            contract = tool_contract.get(transition["tool"], {})
            parameter_name = contract.get("parameter")
            allowed_values = contract.get("allowed_values", [])
            if set(transition["parameters"]) != {parameter_name}:
                errors.append(f"{prefix}.parameters does not match the declared tool contract")
            elif transition["parameters"].get(parameter_name) not in allowed_values:
                errors.append(f"{prefix}.parameters uses a value outside the declared tool contract")
        if transition["outcome"] not in {
            "EFFECT_CONFIRMED",
            "PARTIAL_PROGRESS",
            "HYPOTHESIS_REFUTED",
            "WEAK_NEGATIVE_EVIDENCE",
            "NO_RELEVANT_EFFECT",
            "AGENT_ACTION_ERROR",
            "TOOL_OR_PLATFORM_ERROR",
            "AMBIGUOUS_OBSERVATION",
        }:
            errors.append(f"{prefix}.outcome is not recognized")
        observation = transition["observation"]
        if not isinstance(observation, Mapping) or "evidence_class" not in observation:
            errors.append(f"{prefix}.observation must include evidence_class")
        adaptation = transition["adaptation"]
        if not isinstance(adaptation, Mapping) or not isinstance(adaptation.get("meaningful"), bool):
            errors.append(f"{prefix}.adaptation must include boolean meaningful")
        signature = (
            str(transition["from"]),
            str(transition["tool"]),
            json.dumps(transition["parameters"], sort_keys=True),
        )
        if signature in signatures:
            errors.append(f"{prefix} duplicates a transition signature")
        signatures.add(signature)
    if task["difficulty"]["transition_count"] != len(model["transitions"]):
        errors.append("difficulty.transition_count does not match state model")
    return errors


def _validate_local_safety(task: Mapping[str, Any]) -> list[str]:
    environment = task["environment"]
    errors: list[str] = []
    expected = {
        "kind": "local_finite_state",
        "network": "disabled",
        "external_targets": False,
        "credentials": "none",
        "filesystem": "ephemeral_readonly_fixture",
        "isolation": "per_episode",
    }
    for key, value in expected.items():
        if environment.get(key) != value:
            errors.append(f"environment.{key} must equal {value!r} for local-only pilot safety")
    serialized = json.dumps(task, sort_keys=True).lower()
    forbidden_markers = ("http://", "https://", "ssh://", "subprocess", "socket.", "/bin/", "curl ")
    for marker in forbidden_markers:
        if marker in serialized:
            errors.append(f"task includes forbidden external-execution marker: {marker}")
    return errors


def _validate_reference_behavior(task: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    condition = task["condition"]
    model = task["state_model"]
    contract = task["condition_contract"]
    plan = task["evaluator_only"]["reference_plan"]
    result_one = simulate_plan(task, plan)
    result_two = simulate_plan(task, plan)
    receipt = verify_terminal(task, result_one, agent_claim={"status": "success"})

    if result_one != result_two:
        errors.append("reference plan is non-deterministic")
    if not receipt["passed"]:
        errors.append(f"independent verifier rejected reference plan: {receipt['reason']}")
    if receipt["terminal_outcome"] != task["expected_outcome"]["terminal_outcome"]:
        errors.append("reference plan terminal outcome differs from expected_outcome")
    if result_one.final_state != task["expected_outcome"]["state"]:
        errors.append("reference plan final state differs from expected_outcome.state")

    reachability = reachable_states(task)
    goal_reachable = model["goal_state"] in reachability
    first_action = plan[0] if plan else {}
    evidence = {
        event["observation"]["evidence_class"]
        for event in result_one.events
    }
    strategies = [event["strategy"]["next"] for event in result_one.events]

    if condition == "SOLVABLE":
        if not goal_reachable:
            errors.append("SOLVABLE task has no graph path to its goal state")
        if task["expected_outcome"]["terminal_outcome"] != "VALIDATED_SUCCESS":
            errors.append("SOLVABLE task must expect VALIDATED_SUCCESS")
    elif condition == "DISTRACTOR":
        distractor_action = contract["distractor_action"]
        if not isinstance(contract.get("plausibility_rationale"), str):
            errors.append("DISTRACTOR task must declare why its index route is plausible")
        if not goal_reachable:
            errors.append("DISTRACTOR task has no graph path to its goal state")
        if not isinstance(distractor_action, Mapping):
            errors.append("DISTRACTOR task must declare distractor_action")
        elif not _action_equals(first_action, distractor_action):
            errors.append("DISTRACTOR reference plan must begin with declared distractor_action")
        if not result_one.events or result_one.events[0]["outcome"] != "HYPOTHESIS_REFUTED":
            errors.append("DISTRACTOR first reference action must receive diagnostic refutation")
        if not any(event["adaptation"]["meaningful"] for event in result_one.events[1:]):
            errors.append("DISTRACTOR reference plan lacks meaningful post-refutation adaptation")
        if len(set(strategies)) < 2:
            errors.append("DISTRACTOR reference plan does not change strategy")
        if task["expected_outcome"]["terminal_outcome"] != "VALIDATED_SUCCESS":
            errors.append("DISTRACTOR task must expect VALIDATED_SUCCESS")
    elif condition == "UNSOLVABLE":
        if goal_reachable:
            errors.append("UNSOLVABLE task has a graph path to its goal state")
        if "CONCLUSIVE_UNAVAILABLE" not in evidence:
            errors.append("UNSOLVABLE reference plan lacks conclusive unavailable evidence")
        if task["expected_outcome"]["terminal_outcome"] != "VALIDATED_NON_SUCCESS":
            errors.append("UNSOLVABLE task must expect VALIDATED_NON_SUCCESS")
        if result_one.final_state != model["stop_state"]:
            errors.append("UNSOLVABLE reference plan must end in declared stop_state")
        if not isinstance(contract["unavailability_evidence_state"], str):
            errors.append("UNSOLVABLE task must name unavailability_evidence_state")
    return errors


def validate_task(task: Mapping[str, Any]) -> list[str]:
    """Validate schema shape, safety boundary, state graph, and independent outcome."""

    errors = validate_task_shape(task)
    if errors:
        return errors
    return _validate_transitions(task) + _validate_local_safety(task) + _validate_reference_behavior(task)


def validate_benchmark(task_dir: Path = DEFAULT_TASK_DIR) -> dict[str, Any]:
    """Return a complete audit record for the local pilot, without running an agent."""

    tasks = load_tasks(task_dir)
    task_reports: list[dict[str, Any]] = []
    ids: set[str] = set()
    family_conditions: dict[str, set[str]] = defaultdict(set)
    family_tool_contracts: dict[str, set[str]] = defaultdict(set)
    family_public_contracts: dict[str, set[str]] = defaultdict(set)
    family_transition_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for task in tasks:
        task_id = task.get("task_id", "<missing-task-id>")
        errors = validate_task(task)
        if task_id in ids:
            errors.append("duplicate task_id")
        ids.add(task_id)
        difficulty = task.get("difficulty", {})
        if isinstance(difficulty, Mapping):
            family = str(difficulty.get("family"))
            family_conditions[family].add(str(task.get("condition")))
            family_tool_contracts[family].add(json.dumps(task.get("tool_contract"), sort_keys=True))
            if not errors:
                public = project_agent_task(task).as_mapping()
                public.pop("public_task_id", None)
                family_public_contracts[family].add(json.dumps(public, sort_keys=True))
                family_transition_counts[family][str(task.get("condition"))] = len(task["state_model"]["transitions"])
        task_reports.append(
            {
                "task_id": task_id,
                "condition": task.get("condition"),
                "manifest": str(task_dir / f"{task_id}.json"),
                "passed": not errors,
                "errors": errors,
            }
        )

    condition_counts = Counter(task.get("condition") for task in tasks)
    suite_errors: list[str] = []
    if len(tasks) != 9:
        suite_errors.append(f"pilot must contain exactly 9 tasks, found {len(tasks)}")
    for condition in sorted(TASK_CONDITIONS):
        if condition_counts[condition] != 3:
            suite_errors.append(f"pilot must contain exactly 3 {condition} tasks")
    if len(family_conditions) != 3:
        suite_errors.append("pilot must contain exactly 3 semantic task families")
    for family, conditions in sorted(family_conditions.items()):
        if conditions != TASK_CONDITIONS:
            suite_errors.append(f"family {family!r} must contain all three core conditions")
        if len(family_tool_contracts[family]) != 1:
            suite_errors.append(f"family {family!r} must expose the same tool contract in all conditions")
        if len(family_public_contracts[family]) != 1:
            suite_errors.append(f"family {family!r} has condition-dependent agent-visible task content")

    passed = not suite_errors and all(report["passed"] for report in task_reports)
    return {
        "benchmark_version": "0.1.1",
        "mode": "static_local_validation",
        "agent_runs_launched": 0,
        "passed": passed,
        "task_count": len(tasks),
        "condition_counts": dict(sorted(condition_counts.items())),
        "suite_errors": suite_errors,
        "transition_counts_by_family": dict(sorted(family_transition_counts.items())),
        "difficulty_matched_by_transition_count": all(
            len(set(counts.values())) == 1 for counts in family_transition_counts.values()
        ) if family_transition_counts else False,
        "tasks": task_reports,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the local pilot benchmark without launching agents.")
    parser.add_argument("--task-dir", type=Path, default=DEFAULT_TASK_DIR)
    parser.add_argument("--json", action="store_true", help="Print the complete validation record as JSON.")
    args = parser.parse_args(argv)
    report = validate_benchmark(args.task_dir)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"{status}: {report['task_count']} local pilot tasks; agent_runs_launched=0")
        for item in report["tasks"]:
            if not item["passed"]:
                print(f"  {item['task_id']}: {'; '.join(item['errors'])}")
        for error in report["suite_errors"]:
            print(f"  suite: {error}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
