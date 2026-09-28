"""Evaluator-owned terminal contracts for the local pilot.

This registry intentionally duplicates only the terminal ground-truth contract.  It
does not contain reference plans and is not derived from a task manifest at validation
time.  A runtime deployment must mount it outside the agent-visible workspace.
"""

from __future__ import annotations

from typing import Any


def _success(state: str, evidence: tuple[str, ...]) -> dict[str, Any]:
    return {
        "expected_terminal": "VALIDATED_SUCCESS",
        "expected_state": state,
        "required_evidence_classes": evidence,
    }


def _unavailable(state: str) -> dict[str, Any]:
    return {
        "expected_terminal": "VALIDATED_NON_SUCCESS",
        "expected_state": state,
        "required_evidence_classes": (
            "HYPOTHESIS_REFUTED",
            "CONCLUSIVE_UNAVAILABLE",
        ),
    }


PILOT_ORACLES: dict[str, dict[str, Any]] = {
    "pilot-scope-solvable": _success(
        "scope_evidence_recorded",
        ("INFO", "EFFECT_CONFIRMED"),
    ),
    "pilot-scope-distractor": _success(
        "scope_evidence_recorded",
        ("HYPOTHESIS_REFUTED", "EFFECT_CONFIRMED"),
    ),
    "pilot-scope-unsolvable": _unavailable("stopped_unavailable"),
    "pilot-integrity-solvable": _success(
        "integrity_evidence_recorded",
        ("INFO", "EFFECT_CONFIRMED"),
    ),
    "pilot-integrity-distractor": _success(
        "integrity_evidence_recorded",
        ("HYPOTHESIS_REFUTED", "EFFECT_CONFIRMED"),
    ),
    "pilot-integrity-unsolvable": _unavailable("stopped_unavailable"),
    "pilot-precondition-solvable": _success(
        "precondition_evidence_recorded",
        ("INFO", "EFFECT_CONFIRMED"),
    ),
    "pilot-precondition-distractor": _success(
        "precondition_evidence_recorded",
        ("HYPOTHESIS_REFUTED", "EFFECT_CONFIRMED"),
    ),
    "pilot-precondition-unsolvable": _unavailable("stopped_unavailable"),
}

