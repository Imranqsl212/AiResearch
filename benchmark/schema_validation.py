"""Dependency-free contract checks for pilot task and trajectory records.

The JSON Schema files are the interchange contracts.  These checks deliberately use
only the standard library so a clean checkout can validate the pilot without pulling
in a dependency or running any task environment.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


TASK_CONDITIONS = frozenset({"SOLVABLE", "DISTRACTOR", "UNSOLVABLE"})
SAFE_TOOLS = frozenset({"inspect", "attempt", "terminate"})
TERMINAL_OUTCOMES = frozenset(
    {
        "VALIDATED_SUCCESS",
        "VALIDATED_PARTIAL_SUCCESS",
        "VALIDATED_NON_SUCCESS",
        "UNSUPPORTED_SUCCESS",
        "BUDGET_STOP",
        "TIMEOUT",
        "INFRASTRUCTURE_ABORT",
        "UNKNOWN",
        "INVALID_TASK",
    }
)
ACTION_OUTCOMES = frozenset(
    {
        "EFFECT_CONFIRMED",
        "PARTIAL_PROGRESS",
        "HYPOTHESIS_REFUTED",
        "WEAK_NEGATIVE_EVIDENCE",
        "NO_RELEVANT_EFFECT",
        "AGENT_ACTION_ERROR",
        "TOOL_OR_PLATFORM_ERROR",
        "AMBIGUOUS_OBSERVATION",
    }
)
EVIDENCE_CLASSES = frozenset(
    {
        "INFO",
        "EFFECT_CONFIRMED",
        "HYPOTHESIS_REFUTED",
        "WEAK_NEGATIVE_EVIDENCE",
        "CONCLUSIVE_UNAVAILABLE",
        "NO_RELEVANT_EFFECT",
        "AGENT_ACTION_ERROR",
        "TOOL_OR_PLATFORM_ERROR",
        "AMBIGUOUS_OBSERVATION",
    }
)
ADAPTATION_LEVELS = frozenset(
    {"none", "action", "parameter", "tool", "implementation", "hypothesis", "strategy"}
)
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
TASK_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "condition",
        "objective",
        "task_card",
        "environment",
        "expected_outcome",
        "verifier",
        "difficulty",
        "allowed_tools",
        "tool_contract",
        "timeout_seconds",
        "maximum_steps",
        "version",
        "provenance",
        "condition_contract",
        "state_model",
        "evaluator_only",
    }
)


def _require_mapping(value: Any, path: str, errors: list[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.append(f"{path} must be an object")
        return None
    return value


def _require_string(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")


def _require_fields(
    record: Mapping[str, Any], fields: Sequence[str], path: str, errors: list[str]
) -> None:
    for field in fields:
        if field not in record:
            errors.append(f"{path}.{field} is required")


def validate_task_shape(task: Mapping[str, Any]) -> list[str]:
    """Return shape errors without judging whether a task is actually valid."""

    errors: list[str] = []
    unexpected = sorted(set(task) - TASK_TOP_LEVEL_FIELDS)
    if unexpected:
        errors.append(f"task has unexpected top-level fields: {', '.join(unexpected)}")
    _require_fields(
        task,
        (
            "schema_version",
            "task_id",
            "condition",
            "objective",
            "task_card",
            "environment",
            "expected_outcome",
            "verifier",
            "difficulty",
            "allowed_tools",
            "tool_contract",
            "timeout_seconds",
            "maximum_steps",
            "version",
            "provenance",
            "condition_contract",
            "state_model",
            "evaluator_only",
        ),
        "task",
        errors,
    )
    if task.get("schema_version") != "0.1.0":
        errors.append("task.schema_version must equal 0.1.0")
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        errors.append("task.task_id must be lowercase kebab-case, 3-64 characters")
    if task.get("condition") not in TASK_CONDITIONS:
        errors.append(f"task.condition must be one of {sorted(TASK_CONDITIONS)}")

    objective = _require_mapping(task.get("objective"), "task.objective", errors)
    if objective is not None:
        _require_fields(objective, ("id", "description", "success_criterion"), "task.objective", errors)
        for field in ("id", "description", "success_criterion"):
            if field in objective:
                _require_string(objective[field], f"task.objective.{field}", errors)

    card = _require_mapping(task.get("task_card"), "task.task_card", errors)
    if card is not None:
        _require_fields(card, ("title", "description", "visible_initial_state"), "task.task_card", errors)

    environment = _require_mapping(task.get("environment"), "task.environment", errors)
    if environment is not None:
        _require_fields(
            environment,
            ("kind", "network", "external_targets", "credentials", "filesystem", "isolation"),
            "task.environment",
            errors,
        )

    expected = _require_mapping(task.get("expected_outcome"), "task.expected_outcome", errors)
    if expected is not None:
        _require_fields(expected, ("terminal_outcome", "state"), "task.expected_outcome", errors)
        if expected.get("terminal_outcome") not in TERMINAL_OUTCOMES:
            errors.append("task.expected_outcome.terminal_outcome is invalid")

    verifier = _require_mapping(task.get("verifier"), "task.verifier", errors)
    if verifier is not None:
        _require_fields(verifier, ("id", "expected_terminal", "required_evidence_classes"), "task.verifier", errors)
        if verifier.get("expected_terminal") not in TERMINAL_OUTCOMES:
            errors.append("task.verifier.expected_terminal is invalid")
        evidence = verifier.get("required_evidence_classes")
        if not isinstance(evidence, list) or any(item not in EVIDENCE_CLASSES for item in evidence):
            errors.append("task.verifier.required_evidence_classes must contain known evidence classes")

    difficulty = _require_mapping(task.get("difficulty"), "task.difficulty", errors)
    if difficulty is not None:
        _require_fields(
            difficulty,
            (
                "family",
                "level",
                "transition_count",
                "branching_factor",
                "index_failure_required",
                "difficulty_controls",
            ),
            "task.difficulty",
            errors,
        )

    tools = task.get("allowed_tools")
    if not isinstance(tools, list) or not tools:
        errors.append("task.allowed_tools must be a non-empty list")
    elif any(tool not in SAFE_TOOLS for tool in tools):
        errors.append(f"task.allowed_tools may only contain {sorted(SAFE_TOOLS)}")

    tool_contract = _require_mapping(task.get("tool_contract"), "task.tool_contract", errors)
    if tool_contract is not None:
        if isinstance(tools, list) and set(tool_contract) != set(tools):
            errors.append("task.tool_contract must define exactly the allowed tools")
        for tool, contract in tool_contract.items():
            contract_map = _require_mapping(contract, f"task.tool_contract.{tool}", errors)
            if contract_map is None:
                continue
            _require_fields(contract_map, ("parameter", "allowed_values"), f"task.tool_contract.{tool}", errors)
            _require_string(contract_map.get("parameter"), f"task.tool_contract.{tool}.parameter", errors)
            values = contract_map.get("allowed_values")
            if not isinstance(values, list) or not values or not all(
                isinstance(value, str) and value for value in values
            ):
                errors.append(f"task.tool_contract.{tool}.allowed_values must be a non-empty string list")

    for key in ("timeout_seconds", "maximum_steps"):
        value = task.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            errors.append(f"task.{key} must be a positive integer")

    _require_string(task.get("version"), "task.version", errors)
    provenance = _require_mapping(task.get("provenance"), "task.provenance", errors)
    if provenance is not None:
        _require_fields(provenance, ("source", "created_at", "license", "safety_review"), "task.provenance", errors)

    contract = _require_mapping(task.get("condition_contract"), "task.condition_contract", errors)
    if contract is not None:
        _require_fields(
            contract,
            (
                "index_hypothesis",
                "plausibility_rationale",
                "distractor_action",
                "recovery_action",
                "unavailability_evidence_state",
            ),
            "task.condition_contract",
            errors,
        )
        rationale = contract.get("plausibility_rationale")
        if rationale is not None:
            _require_string(rationale, "task.condition_contract.plausibility_rationale", errors)

    model = _require_mapping(task.get("state_model"), "task.state_model", errors)
    if model is not None:
        _require_fields(
            model,
            ("initial_state", "initial_strategy", "goal_state", "stop_state", "states", "transitions"),
            "task.state_model",
            errors,
        )
        states = model.get("states")
        if not isinstance(states, list) or not all(isinstance(state, str) and state for state in states):
            errors.append("task.state_model.states must be a non-empty string list")
        transitions = model.get("transitions")
        if not isinstance(transitions, list) or not transitions:
            errors.append("task.state_model.transitions must be a non-empty list")

    evaluator_only = _require_mapping(task.get("evaluator_only"), "task.evaluator_only", errors)
    if evaluator_only is not None:
        _require_fields(evaluator_only, ("reference_plan", "unreachability_proof"), "task.evaluator_only", errors)
        if not isinstance(evaluator_only.get("reference_plan"), list):
            errors.append("task.evaluator_only.reference_plan must be a list")

    return errors


def validate_trajectory_shape(trajectory: Mapping[str, Any]) -> list[str]:
    """Return contract errors for a trace without interpreting agent behavior."""

    errors: list[str] = []
    _require_fields(
        trajectory,
        (
            "schema_version",
            "trajectory_id",
            "task_id",
            "task_version",
            "configuration",
            "events",
            "terminal",
        ),
        "trajectory",
        errors,
    )
    if trajectory.get("schema_version") != "0.1.0":
        errors.append("trajectory.schema_version must equal 0.1.0")
    for field in ("trajectory_id", "task_id", "task_version"):
        if field in trajectory:
            _require_string(trajectory[field], f"trajectory.{field}", errors)
    _require_mapping(trajectory.get("configuration"), "trajectory.configuration", errors)
    events = trajectory.get("events")
    if not isinstance(events, list):
        errors.append("trajectory.events must be a list")
        events = []
    for index, event in enumerate(events):
        path = f"trajectory.events[{index}]"
        event_map = _require_mapping(event, path, errors)
        if event_map is None:
            continue
        _require_fields(
            event_map,
            (
                "event_id",
                "sequence",
                "raw_action",
                "tool",
                "parameters",
                "observation",
                "outcome",
                "strategy",
                "adaptation",
                "previous_state",
                "next_state",
            ),
            path,
            errors,
        )
        if not isinstance(event_map.get("sequence"), int) or event_map.get("sequence", 0) < 1:
            errors.append(f"{path}.sequence must be a positive integer")
        elif event_map["sequence"] != index + 1:
            errors.append(f"{path}.sequence must be contiguous and start at 1")
        if event_map.get("tool") not in SAFE_TOOLS:
            errors.append(f"{path}.tool is not an allowed benchmark tool")
        if not isinstance(event_map.get("parameters"), Mapping):
            errors.append(f"{path}.parameters must be an object")
        raw_action = _require_mapping(event_map.get("raw_action"), f"{path}.raw_action", errors)
        if raw_action is not None:
            if raw_action.get("tool") != event_map.get("tool"):
                errors.append(f"{path}.raw_action.tool must equal {path}.tool")
            if raw_action.get("parameters") != event_map.get("parameters"):
                errors.append(f"{path}.raw_action.parameters must equal {path}.parameters")
        observation = _require_mapping(event_map.get("observation"), f"{path}.observation", errors)
        if observation is not None and observation.get("evidence_class") not in EVIDENCE_CLASSES:
            errors.append(f"{path}.observation.evidence_class is invalid")
        if event_map.get("outcome") not in ACTION_OUTCOMES:
            errors.append(f"{path}.outcome is invalid")
        strategy = _require_mapping(event_map.get("strategy"), f"{path}.strategy", errors)
        if strategy is not None:
            _require_fields(strategy, ("previous", "next", "source"), f"{path}.strategy", errors)
        adaptation = _require_mapping(event_map.get("adaptation"), f"{path}.adaptation", errors)
        if adaptation is not None:
            _require_fields(adaptation, ("level", "meaningful", "reason"), f"{path}.adaptation", errors)
            if adaptation.get("level") not in ADAPTATION_LEVELS:
                errors.append(f"{path}.adaptation.level is invalid")
            if not isinstance(adaptation.get("meaningful"), bool):
                errors.append(f"{path}.adaptation.meaningful must be boolean")
        for state_field in ("previous_state", "next_state"):
            _require_string(event_map.get(state_field), f"{path}.{state_field}", errors)

    terminal = _require_mapping(trajectory.get("terminal"), "trajectory.terminal", errors)
    if terminal is not None:
        _require_fields(
            terminal,
            ("agent_claim", "termination_source", "outcome", "verifier_receipt"),
            "trajectory.terminal",
            errors,
        )
        if terminal.get("outcome") not in TERMINAL_OUTCOMES:
            errors.append("trajectory.terminal.outcome is invalid")
        _require_mapping(terminal.get("agent_claim"), "trajectory.terminal.agent_claim", errors)
        if terminal.get("termination_source") not in {
            "AGENT",
            "BUDGET",
            "TIMEOUT",
            "INFRASTRUCTURE",
            "SCRIPTED_FIXTURE",
        }:
            errors.append("trajectory.terminal.termination_source is invalid")
        receipt = _require_mapping(terminal.get("verifier_receipt"), "trajectory.terminal.verifier_receipt", errors)
        if receipt is not None:
            _require_fields(
                receipt,
                (
                    "verifier_id",
                    "verifier_version",
                    "task_id",
                    "passed",
                    "terminal_outcome",
                    "claim_supported",
                    "observed_evidence_classes",
                    "reason",
                ),
                "trajectory.terminal.verifier_receipt",
                errors,
            )

    return errors
