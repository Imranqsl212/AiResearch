"""Adapters from crypto verifier receipts to the trajectory receipt contract."""

from __future__ import annotations

from typing import Any, Mapping


def action_receipt(
    *, task_id: str, action_index: int, verifier_receipt: Mapping[str, Any]
) -> dict[str, Any]:
    """Create the evaluator-owned per-action receipt expected by the logger."""

    passed = bool(verifier_receipt.get("passed"))
    return {
        "source": "evaluator_action_verifier",
        "task_id": task_id,
        "verifier_id": verifier_receipt.get("verifier_id"),
        "verifier_version": verifier_receipt.get("verifier_version"),
        "action_index": action_index,
        "passed": passed,
        "claim_supported": passed,
        "terminal_outcome": "VALIDATED_SUCCESS" if passed else "VALIDATED_NON_SUCCESS",
        "receipt_sha256": verifier_receipt.get("receipt_sha256"),
        "crypto_checks": (verifier_receipt.get("details") or {}).get("checks", {}),
    }


def terminal_receipt(
    *, task_id: str, claim_status: str, verifier_receipt: Mapping[str, Any]
) -> dict[str, Any]:
    """Create the independent terminal receipt consumed by EpisodeRunner."""

    passed = verifier_receipt.get("passed") is True
    terminal_outcome = "VALIDATED_SUCCESS" if passed else "VALIDATED_NON_SUCCESS"
    return {
        "source": "crypto_executable_verifier",
        "task_id": task_id,
        "verifier_id": verifier_receipt.get("verifier_id"),
        "verifier_version": verifier_receipt.get("verifier_version"),
        "passed": passed,
        "claim_supported": claim_status != "success" or passed,
        "terminal_outcome": terminal_outcome,
        "receipt_sha256": verifier_receipt.get("receipt_sha256"),
        "source_sha256": verifier_receipt.get("source_sha256"),
        "failure_reason": verifier_receipt.get("failure_reason"),
        "crypto_checks": (verifier_receipt.get("details") or {}).get("checks", {}),
    }
