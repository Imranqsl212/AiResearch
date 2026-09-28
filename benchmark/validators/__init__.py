"""Independent terminal validators for local benchmark tasks."""

from __future__ import annotations

from typing import Any, Mapping

from benchmark.validators.state_machine import verify_pilot_state_machine


_REGISTRY = {"pilot_state_machine_v1": verify_pilot_state_machine}


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

