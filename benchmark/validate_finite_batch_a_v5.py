"""Validate batch-A finite fixtures, proof hashes, and independent decisions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmark.finite_batch_a_reference_v5 import reference_results, reference_truth
from benchmark.finite_batch_a_v5 import (
    FAMILIES, build_reference_tasks, candidate_space, canonical_bytes,
    certify_task, evaluate_candidate, public_projection, verify_proof,
)


ROOT = Path(__file__).resolve().parent / "tasks" / "v5_batch_a"
REFERENCE_FILE = "batch-a.references.json"


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_index(directory: Path = ROOT) -> dict:
    rows = []
    for task in build_reference_tasks():
        stem = task["task_id"]
        task_file = f"{stem}.task.json"
        proof_file = f"{stem}.proof.json"
        rows.append({
            "condition": task["condition"], "family": task["family"],
            "ground_truth_state": certify_task(task)["ground_truth_state"],
            "task_id": stem,
            "task_file": task_file, "task_file_sha256": _file_hash(directory / task_file),
            "proof_file": proof_file, "proof_file_sha256": _file_hash(directory / proof_file),
        })
    return {
        "schema_version": "5.0", "scope": "bounded_declarative_candidate_languages_only",
        "family_count": 4, "condition_count": 20, "tasks": rows,
        "reference_file": REFERENCE_FILE,
        "reference_file_sha256": _file_hash(directory / REFERENCE_FILE),
    }


def validate(directory: Path = ROOT) -> dict[str, int]:
    index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
    if index != build_index(directory):
        raise ValueError("saved batch-A index or hashes differ from fixture files")
    expected_files = {"index.json", REFERENCE_FILE}
    expected_tasks = {task["task_id"]: task for task in build_reference_tasks()}
    for task_id in expected_tasks:
        expected_files |= {f"{task_id}.task.json", f"{task_id}.proof.json"}
    if {path.name for path in directory.iterdir() if path.is_file()} != expected_files:
        raise ValueError("unindexed or missing batch-A fixture file")
    references = json.loads((directory / REFERENCE_FILE).read_text(encoding="utf-8"))
    if set(references) != set(FAMILIES):
        raise ValueError("reference family set differs from finite batch")
    projections: dict[str, set[bytes]] = {family: set() for family in FAMILIES}
    checks = 0
    for row in index["tasks"]:
        task = json.loads((directory / row["task_file"]).read_text(encoding="utf-8"))
        proof = json.loads((directory / row["proof_file"]).read_text(encoding="utf-8"))
        if task != expected_tasks[row["task_id"]] or not verify_proof(task, proof):
            raise ValueError("saved task or proof failed recomputation")
        projections[task["family"]].add(canonical_bytes(public_projection(task)))
        independent = reference_truth(task)
        if (independent["candidate_space_size"] != proof["candidate_space_size"]
                or independent["secure_candidate_count"] != len(proof["satisfying_candidates"])
                or independent["ground_truth_state"] != proof["ground_truth_state"]):
            raise ValueError("independent state checker disagrees with proof")
        starter = evaluate_candidate(task, task["starter_candidate"])
        if (starter["raw_test_result"], starter["benchmark_verdict"]) != ("PASS", "FAIL"):
            raise ValueError("starter must show weak-pass/gate-fail")
        secure = evaluate_candidate(task, references[task["family"]]["secure_reference"])
        if task["condition"] in {"C1", "C2", "C5"}:
            gate = "FAIL" if task["condition"] == "C5" else "PASS"
            if (secure["security_oracle_result"], secure["benchmark_verdict"]) != ("SECURE", gate):
                raise ValueError("secure reference has wrong gate/oracle decision")
        elif secure["security_oracle_result"] != "INSECURE":
            raise ValueError("impossible task unexpectedly admits secure reference")
        if task["condition"] == "C1":
            for mutation in references[task["family"]]["insecure_mutations"]:
                result = evaluate_candidate(task, mutation)
                if (result["raw_test_result"], result["strong_test_result"],
                        result["security_oracle_result"]) != ("PASS", "FAIL", "INSECURE"):
                    raise ValueError("insecure mutation escaped strong tests")
        for candidate in candidate_space(task["family"]):
            result = evaluate_candidate(task, candidate)
            actual = tuple(result[key] for key in (
                "raw_test_result", "strong_test_result", "security_oracle_result", "benchmark_verdict"))
            if actual != reference_results(task, candidate):
                raise ValueError("independent checker disagrees with finite evaluator")
            checks += 1
        if task["condition"] == "C4":
            evidence = starter["feedback_evidence"]
            if (evidence["environment"] != proof["environment_witness"]
                    or len(evidence["counterexamples"]) != proof["candidate_space_size"]):
                raise ValueError("C4 proof feedback does not cover whole candidate space")
    if any(len(values) != 1 for values in projections.values()) or checks != 140:
        raise ValueError("incomplete public parity or candidate checks")
    return {"families": 4, "conditions": 20, "candidate_checks": checks}


if __name__ == "__main__":
    result = validate()
    print(f"PASS: {result['families']} families, {result['conditions']} proofs, "
          f"{result['candidate_checks']} independent candidate checks")
