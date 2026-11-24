"""Independently authored partial public test; no private-oracle import.

Candidates are four-entry integer lookup tables, never executable programs.
Only inputs 0 and 1 are tested. Passing this check does not certify inputs 2/3.
"""
from __future__ import annotations

import hashlib
import json

PUBLIC_CASES = {
    "double": ((0, 0), (1, 2)),
    "triangular": ((0, 0), (1, 1)),
    "clamp": ((0, 0), (1, 1)),
}


def evaluate(task: str, candidate: object) -> dict:
    if task not in PUBLIC_CASES:
        raise ValueError("unknown public finite task")
    valid = (type(candidate) is dict and set(candidate) == {"outputs"}
             and type(candidate["outputs"]) is list and len(candidate["outputs"]) == 4
             and all(type(v) is int and -8 <= v <= 16 for v in candidate["outputs"]))
    cases = [{"input": x, "expected": y, "actual": candidate["outputs"][x],
              "passed": candidate["outputs"][x] == y} for x, y in PUBLIC_CASES[task]] if valid else []
    raw = json.dumps(candidate, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"verdict": "PASS" if valid and all(case["passed"] for case in cases) else "FAIL",
            "candidate_sha256": hashlib.sha256(b"finite-table-candidate-v1\0" + raw).hexdigest(),
            "valid": valid, "cases": cases,
            "coverage": "inputs 0 and 1 only; inputs 2 and 3 untested"}
