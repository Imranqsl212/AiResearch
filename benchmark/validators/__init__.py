"""Independent terminal validators for local benchmark tasks."""

from __future__ import annotations

from typing import Any, Mapping

from benchmark.validators.state_machine import (
    verify_pilot_action_state_machine,
    verify_pilot_state_machine,
)
from benchmark.validators.four_cell import verify_four_cell_action_receipt, verify_four_cell_receipt
from benchmark.validators.containment_lab import (
    verify_containment_lab_action,
    verify_containment_lab_terminal,
)


_REGISTRY = {
    "pilot_state_machine_v1": verify_pilot_state_machine,
    "containment_lab_state_machine_v1": verify_containment_lab_terminal,
}
_ACTION_REGISTRY = {
    "pilot_state_machine_v1": verify_pilot_action_state_machine,
    "containment_lab_state_machine_v1": verify_containment_lab_action,
}


def verify_terminal(
    task: Mapping[str, Any], result: Any, agent_claim: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Resolve a verifier by immutable manifest ID and return its receipt."""

    verifier_id = task["verifier"]["id"]
    try:
        verifier = _REGISTRY[verifier_id]
    except KeyError as exc:
        raise ValueError(f"Unknown independent verifier: {verifier_id}") from exc
    return verifier(task, result, agent_claim=agent_claim)


def verify_action(task: Mapping[str, Any], result: Any, action_index: int) -> dict[str, Any]:
    """Dispatch an evaluator-owned, completed-prefix verifier by manifest ID."""

    verifier_id = task["verifier"]["id"]
    try:
        verifier = _ACTION_REGISTRY[verifier_id]
    except KeyError as exc:
        raise ValueError(f"Unknown per-action verifier: {verifier_id}") from exc
    return verifier(task, result, action_index)


__all__ = [
    "verify_terminal",
    "verify_action",
    "verify_four_cell_receipt",
    "verify_four_cell_action_receipt",
    "verify_containment_lab_terminal",
    "verify_containment_lab_action",
]
