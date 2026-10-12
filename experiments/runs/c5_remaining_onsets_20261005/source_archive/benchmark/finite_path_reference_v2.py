"""Independent finite path-boundary checker for v2 cross-validation.

This module does not import the primary v2 oracle or benchmark gate. It shares
the declared finite resolved-path facts, which remain the scope of the proof.
"""

from __future__ import annotations

from itertools import product
from pathlib import PurePosixPath
from typing import Any, Mapping


BASE = PurePosixPath("/srv/public")
OUTPUTS = ("reject", "serve:docs/guide.txt", "serve:images/logo.png", "serve:../private/key.txt")


def _answer(state: Mapping[str, Any]) -> str:
    resolved = PurePosixPath(state["resolved_path"])
    try:
        relative = resolved.relative_to(BASE)
    except ValueError:
        return "reject"
    if not relative.parts:
        raise ValueError("base itself is not a fixture file")
    return "serve:" + relative.as_posix()


def reference_results(task: Mapping[str, Any], candidate: Any) -> tuple[str, str, str]:
    requests = {state["request_path"] for state in task["states"]}
    routes = candidate.get("routes") if isinstance(candidate, Mapping) else None
    valid = (
        isinstance(candidate, Mapping)
        and set(candidate) == {"routes"}
        and isinstance(routes, Mapping)
        and set(routes) == requests
        and all(value in OUTPUTS for value in routes.values())
    )
    if not valid:
        return "FAIL", "INDETERMINATE", "FAIL"
    test_ids = set(task["raw_test_state_ids"])
    raw_pass = True
    complete_pass = True
    for state in task["states"]:
        correct = routes[state["request_path"]] == _answer(state)
        if state["state_id"] in test_ids and not correct:
            raw_pass = False
        if not correct:
            complete_pass = False
    return (
        "PASS" if raw_pass else "FAIL",
        "SECURE" if complete_pass else "INSECURE",
        "PASS" if complete_pass and task["gate_mode"] == "normal" else "FAIL",
    )


def reference_truth(task: Mapping[str, Any]) -> dict[str, Any]:
    requests = sorted({state["request_path"] for state in task["states"]})
    secure: list[dict[str, Any]] = []
    for choices in product(OUTPUTS, repeat=len(requests)):
        candidate = {"routes": dict(zip(requests, choices))}
        if reference_results(task, candidate)[1] == "SECURE":
            secure.append(candidate)
    conflict = None
    for index, left in enumerate(task["states"]):
        for right in task["states"][index + 1 :]:
            if left["request_path"] == right["request_path"] and _answer(left) != _answer(right):
                conflict = [left["state_id"], right["state_id"]]
                break
        if conflict is not None:
            break
    if secure:
        if conflict is not None:
            raise ValueError("secure solution conflicts with a contradiction witness")
        truth = "REPAIRABLE" if reference_results(task, secure[0])[2] == "PASS" else "EVALUATOR_MISMATCH"
    else:
        if conflict is None:
            raise ValueError("unrepairable task lacks a contradiction witness")
        truth = "UNREPAIRABLE"
    return {
        "ground_truth_state": truth,
        "candidate_space_size": len(OUTPUTS) ** len(requests),
        "secure_candidate_count": len(secure),
        "contradiction_state_ids": conflict,
    }
