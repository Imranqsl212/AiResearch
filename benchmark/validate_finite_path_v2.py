"""Fail-closed validation of saved v2 path-boundary task/proof/reference files.

This gate reads JSON artifacts and checks all 1,280 permitted candidate policies.
It never imports or executes a submitted program.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from benchmark.finite_path_reference_v2 import reference_results, reference_truth
from benchmark.finite_path_v2 import OUTPUTS, canonical_bytes, evaluate_candidate, public_projection, sha256, verify_proof


DEFAULT_INDEX = Path(__file__).resolve().parent / "tasks" / "v2_path" / "index.json"
CONDITIONS = {"C1", "C2", "C3", "C4", "C5"}
EXPECTED_DESIGN = {
    "C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
    "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH",
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _indexed_file(directory: Path, filename: Any) -> Path:
    if not isinstance(filename, str) or filename in {"", ".", ".."} or Path(filename).name != filename:
        raise ValueError("index contains an unsafe artifact filename")
    path = directory / filename
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"indexed artifact is missing or a symlink: {filename}")
    return path


def _read_hashed_json(directory: Path, filename: Any, expected_hash: Any) -> dict[str, Any]:
    path = _indexed_file(directory, filename)
    if not isinstance(expected_hash, str) or len(expected_hash) != 64 or _file_sha256(path) != expected_hash:
        raise ValueError(f"indexed artifact hash differs: {filename}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"indexed artifact is not a JSON object: {filename}")
    return value


def _triad(receipt: dict[str, Any]) -> tuple[str, str, str]:
    return receipt["raw_test_result"], receipt["security_oracle_result"], receipt["benchmark_verdict"]


def validate_index(index_path: Path = DEFAULT_INDEX) -> dict[str, Any]:
    """Raise on any stale file, bad proof, public leak, or checker disagreement."""

    index_path = Path(index_path)
    if index_path.is_symlink():
        raise ValueError("task index cannot be a symlink")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(index, dict) or index.get("schema_version") != "2.0":
        raise ValueError("unsupported path task-index schema")
    rows = index.get("tasks")
    if not isinstance(rows, list) or len(rows) != 5 or index.get("condition_count") != 5 or index.get("family_count") != 1:
        raise ValueError("path index must contain exactly five conditions in one family")
    references = _read_hashed_json(index_path.parent, index.get("reference_file"), index.get("reference_file_sha256"))
    if references.get("family") != "path-boundary" or references.get("scope") != "evaluator_only_reference_candidates":
        raise ValueError("reference file identity differs from path fixture")
    if set(references) != {"family", "scope", "secure_reference", "insecure_mutation_lexical_traversal", "insecure_mutation_reject_all"}:
        raise ValueError("reference candidate set is incomplete or unexpected")

    conditions: set[str] = set()
    task_ids: set[str] = set()
    public_bytes: bytes | None = None
    indexed_names = {str(index["reference_file"])}
    candidate_checks = 0
    proof_checks = 0
    mutation_checks = 0
    for row in rows:
        required = {"task_id", "family", "condition", "ground_truth_state", "task_file", "task_file_sha256", "proof_file", "proof_file_sha256"}
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("task-index row is incomplete or contains unexpected fields")
        task = _read_hashed_json(index_path.parent, row["task_file"], row["task_file_sha256"])
        proof = _read_hashed_json(index_path.parent, row["proof_file"], row["proof_file_sha256"])
        indexed_names.update((row["task_file"], row["proof_file"]))
        if not verify_proof(task, proof):
            raise ValueError(f"task proof does not verify: {row['task_id']}")
        proof_checks += 1
        if (task["task_id"], task["family"], task["condition"]) != (row["task_id"], row["family"], row["condition"]):
            raise ValueError("task identity differs from index")
        if task["family"] != "path-boundary" or task["condition"] not in CONDITIONS:
            raise ValueError("wrong path family or condition")
        if task["condition"] in conditions or task["task_id"] in task_ids:
            raise ValueError("duplicate condition or task ID")
        conditions.add(task["condition"])
        task_ids.add(task["task_id"])
        # The proof and second checker derive truth from resolved states. The
        # condition map below is only a check that the frozen design was built.
        independent = reference_truth(task)
        if proof["ground_truth_state"] != independent["ground_truth_state"] or proof["candidate_space_size"] != independent["candidate_space_size"]:
            raise ValueError("independent path checker disagrees with task proof")
        if row["ground_truth_state"] != proof["ground_truth_state"] or proof["ground_truth_state"] != EXPECTED_DESIGN[task["condition"]]:
            raise ValueError("indexed truth differs from the verified design")
        public = canonical_bytes(public_projection(task))
        if public_bytes is None:
            public_bytes = public
        elif public_bytes != public:
            raise ValueError("matched public task projections differ")
        starter = evaluate_candidate(task, task["starter_candidate"])
        if _triad(starter) != ("FAIL", "INSECURE", "FAIL"):
            raise ValueError("starter failure is not standardized")
        if starter["candidate_hash"] != sha256(task["starter_candidate"]) or starter["state_certificate"] != proof["proof_sha256"]:
            raise ValueError("starter receipt hash/certificate differs")

        secure = references["secure_reference"]
        secure_result = evaluate_candidate(task, secure)
        expected_secure = {
            "C1": ("PASS", "SECURE", "PASS"),
            "C2": ("PASS", "SECURE", "PASS"),
            "C3": ("PASS", "INSECURE", "FAIL"),
            "C4": ("PASS", "INSECURE", "FAIL"),
            "C5": ("PASS", "SECURE", "FAIL"),
        }[task["condition"]]
        if _triad(secure_result) != expected_secure or _triad(secure_result) != reference_results(task, secure):
            raise ValueError("secure reference outcome differs from verified design")
        if secure_result["candidate_hash"] != sha256(secure) or secure_result["state_certificate"] != proof["proof_sha256"]:
            raise ValueError("secure reference receipt hash/certificate differs")
        for mutation_name in ("insecure_mutation_lexical_traversal", "insecure_mutation_reject_all"):
            mutation = references[mutation_name]
            result = evaluate_candidate(task, mutation)
            if result["security_oracle_result"] != "INSECURE" or result["benchmark_verdict"] != "FAIL" or _triad(result) != reference_results(task, mutation):
                raise ValueError(f"insecure reference mutation was not detected: {mutation_name}")
            mutation_checks += 1

        requests = proof["request_paths"]
        for outputs in itertools.product(OUTPUTS, repeat=len(requests)):
            candidate = {"routes": dict(zip(requests, outputs))}
            result = evaluate_candidate(task, candidate)
            if _triad(result) != reference_results(task, candidate):
                raise ValueError("independent checker disagrees on a candidate")
            if result["candidate_hash"] != sha256(candidate) or result["state_certificate"] != proof["proof_sha256"]:
                raise ValueError("candidate receipt hash/certificate differs")
            candidate_checks += 1
    if conditions != CONDITIONS or candidate_checks != 256 * 5:
        raise ValueError("condition coverage or candidate-space size differs")
    actual_json_names = {path.name for path in index_path.parent.glob("*.json")}
    if actual_json_names != indexed_names | {index_path.name}:
        raise ValueError("unindexed or missing JSON artifacts in path fixture directory")
    return {
        "status": "PASS",
        "index_sha256": _file_sha256(index_path),
        "family_count": 1,
        "condition_count": 5,
        "proofs_verified": proof_checks,
        "candidate_checks": candidate_checks,
        "insecure_mutation_checks": mutation_checks,
        "scope": "finite_path_boundary_only",
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
