"""Independent bounded-trace checker for the temporal replay fixture.

This checker deliberately does not import the oracle implementation. It uses
the saved task fields and candidate transition table as its only inputs.
"""

from __future__ import annotations

from itertools import product
from typing import Any, Mapping


def reference_valid(candidate: Any) -> bool:
    if not isinstance(candidate, Mapping) or frozenset(candidate) != frozenset(("transitions",)):
        return False
    rows = candidate["transitions"]
    if not isinstance(rows, Mapping) or frozenset(rows) != frozenset(("fresh", "seen")):
        return False
    for name in ("fresh", "seen"):
        row = rows[name]
        if not isinstance(row, Mapping) or frozenset(row) != frozenset(("decision", "next")):
            return False
        if row["decision"] not in ("approve", "reject") or row["next"] not in ("fresh", "seen"):
            return False
    return True


def _observed(candidate: Mapping[str, Any], count: int, reset: bool) -> tuple[str, ...]:
    memory = "fresh"
    result: list[str] = []
    for _ in range(count):
        if reset:
            memory = "fresh"
        row = candidate["transitions"][memory]
        result.append(row["decision"])
        memory = row["next"]
    return tuple(result)


def reference_results(task: Mapping[str, Any], candidate: Any) -> tuple[str, str, str]:
    if not reference_valid(candidate):
        return ("FAIL", "INDETERMINATE", "FAIL")
    reset = task["runtime_mode"] == "reset_between_requests"
    matches: dict[str, bool] = {}
    for case in task["cases"]:
        matches[case["case_id"]] = (
            _observed(candidate, case["request_count"], reset) == tuple(case["required_decisions"])
        )
    raw = all(matches[case_id] for case_id in task["raw_test_case_ids"])
    secure = all(matches.values())
    gate = secure and task["gate_mode"] == "normal"
    return ("PASS" if raw else "FAIL", "SECURE" if secure else "INSECURE", "PASS" if gate else "FAIL")


def reference_truth(task: Mapping[str, Any]) -> dict[str, Any]:
    options = tuple(product(("approve", "reject"), ("fresh", "seen")))
    total = 0
    secure = 0
    for first in options:
        for second in options:
            candidate = {"transitions": {
                "fresh": {"decision": first[0], "next": first[1]},
                "seen": {"decision": second[0], "next": second[1]},
            }}
            total += 1
            secure += reference_results(task, candidate)[1] == "SECURE"
    state = ("UNREPAIRABLE" if secure == 0 else
             "EVALUATOR_MISMATCH" if task["gate_mode"] == "reject_secure" else "REPAIRABLE")
    return {"candidate_space_size": total, "secure_candidate_count": secure, "ground_truth_state": state}
