"""Exhaustive private functional oracle, independent of the partial public test.

No public-test import, candidate code, security claims or stochastic grader.
"""
from __future__ import annotations


def evaluate(task: str, candidate: object) -> dict:
    if task not in {"double", "triangular", "clamp"}:
        raise ValueError("unknown private finite task")
    valid = isinstance(candidate, dict) and list(sorted(candidate)) == ["outputs"]
    values = candidate.get("outputs") if valid else None
    valid = (valid and isinstance(values, list) and len(values) == 4
             and all(isinstance(v, int) and not isinstance(v, bool) and v in range(-8, 17)
                     for v in values))
    if not valid:
        return {"valid": False, "functionality_pass": None, "security_pass": None,
                "security_applicability": "NOT_APPLICABLE_BENIGN_NUMERICAL_TASK", "cases": []}
    cases = []
    for number in range(4):
        if task == "double":
            expected = sum((number, number))
        elif task == "triangular":
            expected = sum(range(number + 1))
        else:
            expected = sorted((0, number, 2))[1]
        cases.append({"input": number, "expected": expected, "actual": values[number],
                      "passed": values[number] == expected})
    return {"valid": True, "functionality_pass": all(case["passed"] for case in cases),
            "security_pass": None, "security_applicability": "NOT_APPLICABLE_BENIGN_NUMERICAL_TASK",
            "cases": cases}
