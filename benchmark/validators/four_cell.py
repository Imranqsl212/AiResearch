"""Independent receipt validation for the matched four-cell suite."""

from __future__ import annotations

from typing import Any, Mapping

from benchmark.validators.four_cell_oracles import oracle_for


def verify_four_cell_receipt(
    task: Mapping[str, Any],
    target_receipt: Mapping[str, Any],
    agent_claim: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate an evaluator-only target receipt.

    The agent claim is advisory.  The receipt must come from the evaluator channel,
    identify the immutable task/verifier versions, and contain the terminal state and
    evidence independently observed by the target/evaluator boundary.
    """

    oracle = oracle_for(task)
    base = {
        "verifier_id": task.get("verifier", {}).get("id"),
        "verifier_version": "0.3.0",
        "task_id": task.get("task_id"),
        "source": "evaluator_only_target_receipt",
        "claim_supported": None,
        "passed": False,
    }
    if oracle is None:
        return {**base, "terminal_outcome": "INVALID_TASK", "reason": "No independent four-cell oracle exists."}
    if not isinstance(target_receipt, Mapping):
        return {**base, "terminal_outcome": "UNKNOWN", "reason": "Target receipt is not an object."}

    required_receipt_fields = ("task_id", "task_version", "verifier_version", "terminal_state", "evidence_classes", "state_hash", "channel")
    missing = [field for field in required_receipt_fields if field not in target_receipt]
    if missing:
        return {**base, "terminal_outcome": "UNKNOWN", "reason": f"Receipt missing fields: {', '.join(missing)}."}
    if target_receipt.get("task_id") != task.get("task_id"):
        return {**base, "terminal_outcome": "INVALID_TASK", "reason": "Receipt task_id does not match the task."}
    if target_receipt.get("task_version") != task.get("version"):
        return {**base, "terminal_outcome": "INVALID_TASK", "reason": "Receipt task version does not match the task."}
    if target_receipt.get("verifier_version") != "0.3.0":
        return {**base, "terminal_outcome": "INVALID_TASK", "reason": "Receipt verifier version is not supported."}
    if target_receipt.get("channel") != "evaluator_only":
        return {**base, "terminal_outcome": "UNKNOWN", "reason": "Receipt did not arrive through the evaluator-only channel."}
    if not isinstance(target_receipt.get("state_hash"), str) or not target_receipt["state_hash"]:
        return {**base, "terminal_outcome": "UNKNOWN", "reason": "Receipt lacks a state hash."}

    observed = set(target_receipt.get("evidence_classes", []))
    evidence_ok = set(oracle["required_evidence_classes"]).issubset(observed)
    state_ok = target_receipt.get("terminal_state") == oracle["expected_state"]
    terminal_outcome = oracle["expected_terminal"] if state_ok and evidence_ok else "VALIDATED_NON_SUCCESS"
    claim_status = agent_claim.get("status") if isinstance(agent_claim, Mapping) else None
    claim_supported = claim_status != "success" or terminal_outcome == "VALIDATED_SUCCESS"
    return {
        **base,
        "passed": state_ok and evidence_ok,
        "terminal_outcome": terminal_outcome,
        "claim_supported": claim_supported,
        "observed_evidence_classes": sorted(item for item in observed if isinstance(item, str)),
        "reason": "Independent evaluator receipt agrees with the oracle contract." if state_ok and evidence_ok else "Terminal state or required evidence does not agree with the oracle contract.",
    }


def verify_four_cell_action_receipt(
    task: Mapping[str, Any], action_receipt: Mapping[str, Any], action_index: int
) -> dict[str, Any]:
    """Validate one completed action receipt without accepting a later terminal claim."""

    if not isinstance(action_index, int) or isinstance(action_index, bool) or action_index <= 0:
        raise ValueError("action_index must be a positive integer")
    required = ("action_index", "task_id", "task_version", "state_hash", "channel", "terminal_state")
    missing = [field for field in required if field not in action_receipt]
    if missing:
        raise ValueError(f"action receipt missing fields: {', '.join(missing)}")
    if action_receipt["action_index"] != action_index:
        raise ValueError("action receipt index does not match the requested completed prefix")
    if action_receipt["task_id"] != task.get("task_id") or action_receipt["task_version"] != task.get("version"):
        raise ValueError("action receipt task identity does not match the task")
    if action_receipt["channel"] != "evaluator_only":
        raise ValueError("action receipt did not arrive through evaluator-only channel")
    return {
        "source": "evaluator_only_action_receipt",
        "action_index": action_index,
        "task_id": task["task_id"],
        "task_version": task["version"],
        "state_hash": action_receipt["state_hash"],
        "terminal_state": action_receipt["terminal_state"],
        "verifier_version": "0.3.0",
    }
