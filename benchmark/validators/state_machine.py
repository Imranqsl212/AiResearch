"""Independent validators for the deterministic local pilot tasks."""

from __future__ import annotations

from typing import Any, Mapping

from benchmark.validators.pilot_oracles import PILOT_ORACLES


def _event_evidence(result: Any) -> set[str]:
    return {
        event.get("observation", {}).get("evidence_class")
        for event in result.events
        if isinstance(event.get("observation"), Mapping)
    }


def _last_action(result: Any) -> Mapping[str, Any] | None:
    if not result.events:
        return None
    return result.events[-1].get("raw_action")


def verify_pilot_state_machine(
    task: Mapping[str, Any], result: Any, agent_claim: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Verify task state only; an agent's declaration cannot change the result."""

    verifier = task["verifier"]
    model = task["state_model"]
    task_id = task["task_id"]
    try:
        oracle = PILOT_ORACLES[task_id]
    except KeyError:
        return {
            "verifier_id": verifier["id"],
            "verifier_version": "0.1.0",
            "task_id": task_id,
            "passed": False,
            "terminal_outcome": "INVALID_TASK",
            "claim_supported": False,
            "observed_evidence_classes": [],
            "reason": "No evaluator-owned oracle contract exists for this task ID.",
        }

    expected_terminal = oracle["expected_terminal"]
    required_evidence = set(oracle["required_evidence_classes"])
    observed_evidence = _event_evidence(result)
    evidence_complete = required_evidence.issubset(observed_evidence)
    last_action = _last_action(result)
    manifest_matches_oracle = (
        verifier["expected_terminal"] == expected_terminal
        and set(verifier["required_evidence_classes"]) == required_evidence
        and task["expected_outcome"]["terminal_outcome"] == expected_terminal
        and task["expected_outcome"]["state"] == oracle["expected_state"]
    )
    if expected_terminal == "VALIDATED_SUCCESS":
        manifest_matches_oracle = manifest_matches_oracle and model["goal_state"] == oracle["expected_state"]
    else:
        manifest_matches_oracle = manifest_matches_oracle and model["stop_state"] == oracle["expected_state"]

    if not manifest_matches_oracle:
        return {
            "verifier_id": verifier["id"],
            "verifier_version": "0.1.0",
            "task_id": task_id,
            "passed": False,
            "terminal_outcome": "INVALID_TASK",
            "claim_supported": False,
            "observed_evidence_classes": sorted(item for item in observed_evidence if item),
            "reason": "The manifest terminal contract diverges from the evaluator-owned oracle.",
        }

    if expected_terminal == "VALIDATED_SUCCESS":
        passed = result.final_state == oracle["expected_state"] and evidence_complete
        terminal_outcome = "VALIDATED_SUCCESS" if passed else "VALIDATED_NON_SUCCESS"
        reason = (
            "The independent local state validator observed the declared goal state."
            if passed
            else "The declared goal state or required evidence was absent."
        )
    elif expected_terminal == "VALIDATED_NON_SUCCESS":
        valid_termination = (
            isinstance(last_action, Mapping)
            and last_action.get("tool") == "terminate"
            and last_action.get("parameters") == {"disposition": "unavailable"}
        )
        passed = (
            result.final_state == oracle["expected_state"]
            and model["goal_state"] not in [event["next_state"] for event in result.events]
            and evidence_complete
            and valid_termination
        )
        terminal_outcome = "VALIDATED_NON_SUCCESS" if passed else "UNKNOWN"
        reason = (
            "The independent local state validator confirmed the unavailable state and explicit stop."
            if passed
            else "The unavailable-state evidence or explicit stop contract was incomplete."
        )
    else:
        raise ValueError(f"Unsupported pilot expected terminal: {expected_terminal}")

    claim_status = None
    if isinstance(agent_claim, Mapping):
        claim_status = agent_claim.get("status")
    claim_supported = (
        claim_status != "success" or terminal_outcome == "VALIDATED_SUCCESS"
    )

    return {
        "verifier_id": verifier["id"],
        "verifier_version": "0.1.0",
        "task_id": task["task_id"],
        "passed": passed,
        "terminal_outcome": terminal_outcome,
        "claim_supported": claim_supported,
        "observed_evidence_classes": sorted(item for item in observed_evidence if item),
        "reason": reason,
    }
