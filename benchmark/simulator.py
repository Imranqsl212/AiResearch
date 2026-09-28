"""A deterministic, in-memory state-machine executor for benchmark self-validation.

It exists to test task contracts and reference plans.  It is not an agent runner and
offers no shell, network, filesystem mutation, credential, or process capability.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from benchmark.schema_validation import validate_trajectory_shape


@dataclass(frozen=True)
class SimulationResult:
    """The local result supplied to an independent verifier."""

    final_state: str
    final_strategy: str
    events: tuple[dict[str, Any], ...]


def _action_parts(action: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    tool = action.get("tool")
    parameters = action.get("parameters", {})
    if not isinstance(tool, str):
        tool = ""
    if not isinstance(parameters, Mapping):
        parameters = {}
    return tool, dict(parameters)


def _matching_transition(
    task: Mapping[str, Any], current_state: str, tool: str, parameters: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    transitions = task["state_model"]["transitions"]
    for transition in transitions:
        if (
            transition.get("from") == current_state
            and transition.get("tool") == tool
            and transition.get("parameters") == dict(parameters)
        ):
            return transition
    return None


def simulate_plan(task: Mapping[str, Any], plan: Sequence[Mapping[str, Any]]) -> SimulationResult:
    """Apply an evaluator-supplied plan to a purely declarative local task."""

    model = task["state_model"]
    current_state = model["initial_state"]
    current_strategy = model["initial_strategy"]
    events: list[dict[str, Any]] = []

    for sequence, action in enumerate(plan, start=1):
        tool, parameters = _action_parts(action)
        previous_state = current_state
        previous_strategy = current_strategy
        transition = _matching_transition(task, current_state, tool, parameters)

        if transition is None:
            observation = {
                "kind": "invalid_action",
                "evidence_class": "AGENT_ACTION_ERROR",
                "message": "The requested local simulator transition is unavailable from this state.",
            }
            outcome = "AGENT_ACTION_ERROR"
            next_state = current_state
            next_strategy = current_strategy
            adaptation = {
                "level": "none",
                "meaningful": False,
                "reason": "No declared local transition matched the action.",
            }
        else:
            observation = deepcopy(transition["observation"])
            outcome = transition["outcome"]
            next_state = transition["to"]
            next_strategy = transition["strategy"]
            adaptation = deepcopy(transition["adaptation"])

        events.append(
            {
                "event_id": f"evt-{sequence:04d}",
                "sequence": sequence,
                "raw_action": {"tool": tool, "parameters": deepcopy(parameters)},
                "tool": tool,
                "parameters": deepcopy(parameters),
                "observation": observation,
                "outcome": outcome,
                "strategy": {
                    "previous": previous_strategy,
                    "next": next_strategy,
                    "source": "task_manifest",
                },
                "adaptation": adaptation,
                "previous_state": previous_state,
                "next_state": next_state,
            }
        )
        current_state = next_state
        current_strategy = next_strategy

    return SimulationResult(
        final_state=current_state,
        final_strategy=current_strategy,
        events=tuple(events),
    )


def build_trajectory(
    task: Mapping[str, Any],
    plan: Sequence[Mapping[str, Any]],
    trajectory_id: str,
    configuration: Mapping[str, Any] | None = None,
    agent_claim: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a schema-conformant synthetic trace for fixtures and validator tests."""

    from benchmark.validators import verify_terminal

    result = simulate_plan(task, plan)
    receipt = verify_terminal(task, result, agent_claim=agent_claim)
    trajectory = {
        "schema_version": "0.1.0",
        "trajectory_id": trajectory_id,
        "task_id": task["task_id"],
        "task_version": task["version"],
        "configuration": dict(configuration or {"kind": "scripted_fixture"}),
        "events": list(result.events),
        "terminal": {
            "agent_claim": dict(agent_claim or {"status": "unspecified"}),
            "termination_source": "SCRIPTED_FIXTURE",
            "outcome": receipt["terminal_outcome"],
            "verifier_receipt": receipt,
        },
    }
    errors = validate_trajectory_shape(trajectory)
    if errors:
        raise ValueError("Synthetic trajectory violated its contract: " + "; ".join(errors))
    return trajectory


def reachable_states(task: Mapping[str, Any]) -> set[str]:
    """Compute graph reachability without executing an agent or any external program."""

    transitions = task["state_model"]["transitions"]
    discovered = {task["state_model"]["initial_state"]}
    frontier = list(discovered)
    while frontier:
        state = frontier.pop()
        for transition in transitions:
            if transition.get("from") == state and transition.get("to") not in discovered:
                discovered.add(transition["to"])
                frontier.append(transition["to"])
    return discovered

