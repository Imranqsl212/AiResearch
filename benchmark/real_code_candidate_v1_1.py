"""Corrected excluded real-code candidate: C3 generic, C4 certificate.

Version 1.0 is retained byte-for-byte for audit. This module changes only the
feedback contrast and versioned contracts, with zero model or Docker calls.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from benchmark import real_code_candidate_v1 as previous


VERSION = "real-code-candidate-v1.1.0"
STATUS = previous.STATUS
SUPERSEDED_INDEX_SHA256 = "5e042f648ec63bf4ff7726d60649b1f59cdb788a93b96321f05fb26ebe823732"
GENERIC_FAILURE = {
    "kind": "security_check",
    "status": "failed",
    "message": "The independent checker did not accept this implementation.",
}


def public_projection(family: str) -> dict[str, Any]:
    projection = deepcopy(previous.public_projection(family))
    projection["version"] = VERSION
    return projection


def feedback_receipt(family: str, condition: str) -> dict[str, Any]:
    """Design-level feedback, never a claim about a live model attempt."""

    if family not in previous.FAMILY_CONFIG or condition not in previous.CONDITIONS:
        raise ValueError("unknown family or condition")
    if condition in {"C1", "C3"}:
        # Both failures are truthful. C3 never reveals the absent capability,
        # its probe, or the contradiction witness to the agent.
        return dict(GENERIC_FAILURE)
    if condition == "C4":
        receipt = previous.feedback_receipt(family, "C4")
        return {**receipt, "kind": "security_check",
                "certificate_scope": "offline_authored_fixture_only"}
    return {"status": "REQUIRES_ACTUAL_CANDIDATE_AND_ORACLE_RECEIPT"}


def build_contract(family: str) -> dict[str, Any]:
    contract = deepcopy(previous.build_contract(family))
    contract["schema_version"] = VERSION
    contract["public_task"] = public_projection(family)
    contract["supersedes_index_sha256"] = SUPERSEDED_INDEX_SHA256
    contract["conditions"]["C1"]["feedback"] = "generic_truthful_failure"
    contract["conditions"]["C3"]["feedback"] = "generic_truthful_failure_no_absence_disclosure"
    contract["conditions"]["C4"]["feedback"] = "verified_bounded_impossibility_certificate"
    return contract


def validate_candidate() -> dict[str, Any]:
    report = previous.validate_candidate()
    if report["status"] != STATUS or report["family_count"] != 2:
        raise ValueError("base calibration or family inventory differs")
    for family in previous.FAMILY_CONFIG:
        contract = build_contract(family)
        cells = contract["conditions"]
        if (set(cells) != set(previous.CONDITIONS)
                or feedback_receipt(family, "C1") != feedback_receipt(family, "C3")
                or any(marker in str(feedback_receipt(family, "C3")).lower()
                       for marker in ("absent", "resource", "capability", "witness", "probe"))
                or "verifiable_witness" not in feedback_receipt(family, "C4")
                or cells["C3"]["resource_present"] is not False
                or cells["C4"]["resource_present"] is not False
                or cells["C5"]["resource_present"] is not True):
            raise ValueError("v1.1 feedback or resource contrast differs")
    return {**report, "schema_version": VERSION,
            "supersedes_index_sha256": SUPERSEDED_INDEX_SHA256,
            "c3_feedback": "GENERIC_TRUTHFUL_FAILURE",
            "c4_feedback": "BOUNDED_IMPOSSIBILITY_CERTIFICATE",
            "main_ready": False, "model_calls": 0}


if __name__ == "__main__":
    import json
    print(json.dumps(validate_candidate(), sort_keys=True, indent=2))
