"""Validate every saved finite-policy v1 task/proof pair and its public parity.

This is an engineering gate for the one-family fixture, not a general security
certificate. It reads local JSON and never executes submitted source code.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from benchmark.finite_policy_reference import reference_results, reference_truth
from benchmark.finite_policy_v1 import canonical_bytes, evaluate_candidate, public_projection, verify_proof


DEFAULT_INDEX = Path(__file__).resolve().parent / "tasks" / "v1" / "index.json"
CONDITIONS = {"C1", "C2", "C3", "C4", "C5"}
EXPECTED_STATES = {
    "C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
    "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _indexed_file(directory: Path, name: Any) -> Path:
    if not isinstance(name, str) or name in {"", ".", ".."} or Path(name).name != name:
        raise ValueError("index contains an unsafe artifact filename")
    path = directory / name
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"indexed artifact is missing or a symlink: {name}")
    return path


def validate_index(index_path: Path = DEFAULT_INDEX) -> dict[str, Any]:
    """Raise on any stale, invalid, unmatched, or internally discordant task."""

    index_path = Path(index_path)
    if index_path.is_symlink():
        raise ValueError("task index cannot be a symlink")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(index, dict) or index.get("schema_version") != "1.0":
        raise ValueError("unsupported task-index schema")
    rows = index.get("tasks")
    if not isinstance(rows, list) or not rows:
        raise ValueError("task index contains no tasks")
    if index.get("condition_count") != len(rows):
        raise ValueError("condition count does not match index")
    families: dict[str, set[str]] = {}
    public_by_family: dict[str, bytes] = {}
    ids: set[str] = set()
    candidate_checks = 0
    for row in rows:
        if not isinstance(row, dict) or not {"task_id", "family", "condition", "ground_truth_state", "task_file", "task_file_sha256", "proof_file", "proof_file_sha256"} <= row.keys():
            raise ValueError("task-index row is incomplete")
        task_path = _indexed_file(index_path.parent, row["task_file"])
        proof_path = _indexed_file(index_path.parent, row["proof_file"])
        if _sha256(task_path) != row["task_file_sha256"] or _sha256(proof_path) != row["proof_file_sha256"]:
            raise ValueError("indexed task/proof file hash differs")
        task = json.loads(task_path.read_text(encoding="utf-8"))
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        if not isinstance(task, dict) or not isinstance(proof, dict) or not verify_proof(task, proof):
            raise ValueError("task proof does not verify")
        if task["task_id"] != row["task_id"] or task["family"] != row["family"] or task["condition"] != row["condition"]:
            raise ValueError("task identity differs from index")
        if task["task_id"] in ids:
            raise ValueError("duplicate task ID")
        ids.add(task["task_id"])
        if proof["ground_truth_state"] != row["ground_truth_state"] or proof["ground_truth_state"] != EXPECTED_STATES[task["condition"]]:
            raise ValueError("task truth differs from independent condition plan")
        reference = reference_truth(task)
        if reference["ground_truth_state"] != proof["ground_truth_state"] or reference["candidate_space_size"] != proof["candidate_space_size"]:
            raise ValueError("reference checker disagrees with proof")
        public = canonical_bytes(public_projection(task))
        previous = public_by_family.setdefault(task["family"], public)
        if public != previous:
            raise ValueError("matched public task projections differ within family")
        families.setdefault(task["family"], set()).add(task["condition"])
        starter = evaluate_candidate(task, task["starter_candidate"])
        if (starter["raw_test_result"], starter["security_oracle_result"], starter["benchmark_verdict"]) != ("FAIL", "INSECURE", "FAIL"):
            raise ValueError("starter failure is not standardized")
        keys = proof["observation_keys"]
        for values in itertools.product(("deny", "allow"), repeat=len(keys)):
            candidate = {"decisions": dict(zip(keys, values))}
            observed = evaluate_candidate(task, candidate)
            independent = reference_results(task, candidate)
            if (observed["raw_test_result"], observed["security_oracle_result"], observed["benchmark_verdict"]) != independent:
                raise ValueError("reference checker disagrees with evaluator")
            candidate_checks += 1
    if index.get("family_count") != len(families) or any(conditions != CONDITIONS for conditions in families.values()):
        raise ValueError("families are incomplete or family count differs")
    return {
        "status": "PASS", "index_sha256": _sha256(index_path),
        "family_count": len(families), "condition_count": len(rows),
        "candidate_checks": candidate_checks, "proofs_verified": len(rows),
        "scope": "finite_policy_domain_only",
    }


def main() -> int:
    try:
        report = validate_index()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
