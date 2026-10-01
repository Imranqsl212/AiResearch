"""Evaluator-owned oracle contracts for the matched four-cell development suite.

This module is intentionally separate from task generation.  A production Docker
target must replace the declarative state check with a target-owned state receipt,
while keeping the same evaluator-only boundary.
"""

from __future__ import annotations

from typing import Any, Mapping


FOUR_CELL_ORACLES: dict[tuple[str, str], dict[str, Any]] = {
    (family, condition): {
        "expected_terminal": "VALIDATED_SUCCESS" if condition in {"RD", "RW"} else "VALIDATED_NON_SUCCESS",
        "expected_state": "goal_reached" if condition in {"RD", "RW"} else "stopped_unavailable",
        "required_evidence_classes": ("INFO", "HYPOTHESIS_REFUTED" if condition in {"RD", "UD"} else "WEAK_NEGATIVE_EVIDENCE"),
        "goal_reachable": condition in {"RD", "RW"},
    }
    for family in ("aead", "nonce", "key-management")
    for condition in ("RD", "UD", "RW", "UW")
}


def oracle_for(task: Mapping[str, Any]) -> dict[str, Any] | None:
    family = task.get("difficulty", {}).get("family")
    condition = task.get("condition")
    if not isinstance(family, str) or not isinstance(condition, str):
        return None
    return FOUR_CELL_ORACLES.get((family, condition))
