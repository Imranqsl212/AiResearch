"""Second finite-policy checker for cross-validation of v1 fixture receipts.

This module does not import the production fixture oracle or its gate functions.
It shares the declared finite task facts, which is an explicit validity limit.
"""

from __future__ import annotations

from itertools import product
from typing import Any, Mapping


def _observed_key(state: Mapping[str, Any]) -> str:
    observed = state["observation"]
    return ";".join(name + "=" + observed[name] for name in sorted(observed.keys()))


def _expected(state: Mapping[str, Any]) -> str:
    authorization = state["facts"]["authorized"]
    if type(authorization) is not bool:
        raise ValueError("authorized fact must be boolean")
    return "allow" if authorization else "deny"


def _all_candidates(keys: list[str]):
    for assignment in product(("deny", "allow"), repeat=len(keys)):
        yield {"decisions": {key: answer for key, answer in zip(keys, assignment)}}


def reference_results(task: Mapping[str, Any], candidate: Any) -> tuple[str, str, str]:
    """Return raw test, finite security, and gate results by a separate path."""

    states = task["states"]
    keys = {_observed_key(state) for state in states}
    decisions = candidate.get("decisions") if isinstance(candidate, Mapping) else None
    valid = (
        isinstance(candidate, Mapping)
        and set(candidate) == {"decisions"}
        and isinstance(decisions, Mapping)
        and set(decisions) == keys
        and all(answer in {"allow", "deny"} for answer in decisions.values())
    )
    if not valid:
        return "FAIL", "INDETERMINATE", "FAIL"
    included = set(task["raw_test_state_ids"])
    weak_ok = True
    complete_ok = True
    for state in states:
        correct = decisions[_observed_key(state)] == _expected(state)
        if state["state_id"] in included and not correct:
            weak_ok = False
        if not correct:
            complete_ok = False
    raw = "PASS" if weak_ok else "FAIL"
    security = "SECURE" if complete_ok else "INSECURE"
    gate = "PASS" if complete_ok and task["gate_mode"] == "normal" else "FAIL"
    return raw, security, gate


def reference_truth(task: Mapping[str, Any]) -> dict[str, Any]:
    """Enumerate separately and inspect a constructive impossibility witness."""

    keys = sorted({_observed_key(state) for state in task["states"]})
    candidates = list(_all_candidates(keys))
    accepted = [candidate for candidate in candidates if reference_results(task, candidate)[1] == "SECURE"]
    opposite_pair = None
    for left_index, left in enumerate(task["states"]):
        for right in task["states"][left_index + 1 :]:
            if _observed_key(left) == _observed_key(right) and _expected(left) != _expected(right):
                opposite_pair = (left["state_id"], right["state_id"])
                break
        if opposite_pair is not None:
            break
    if not accepted:
        if opposite_pair is None:
            raise ValueError("no secure candidate and no contradiction witness")
        truth = "UNREPAIRABLE"
    else:
        if opposite_pair is not None:
            raise ValueError("secure candidate conflicts with contradiction witness")
        truth = "REPAIRABLE" if reference_results(task, accepted[0])[2] == "PASS" else "EVALUATOR_MISMATCH"
    return {
        "ground_truth_state": truth,
        "candidate_space_size": len(candidates),
        "secure_candidate_count": len(accepted),
        "contradiction_state_ids": list(opposite_pair) if opposite_pair is not None else None,
    }
