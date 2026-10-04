"""Fail-closed audit of the four saved v5 finite task/proof families."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmark.finite_batch_b_reference_v5 import reference_results, reference_truth
from benchmark.finite_batch_b_v5 import (
    FAMILIES, build_reference_tasks, candidate_space, canonical_bytes, certify_task,
    evaluate_candidate, public_projection, verify_proof,
)


ROOT = Path(__file__).resolve().parent / "tasks" / "v5_batch_b"
REFERENCE_FILE = "batch-b.references.json"
EXPECTED_STATES = {"C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
                   "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH"}


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
            "task_id": stem, "task_file": task_file, "task_file_sha256": _file_hash(directory / task_file),
            "proof_file": proof_file, "proof_file_sha256": _file_hash(directory / proof_file),
        })
    return {
        "schema_version": "5.0", "scope": "finite_candidate_languages_and_listed_cases_only",
        "family_count": len(FAMILIES), "condition_count": len(rows), "tasks": rows,
        "reference_file": REFERENCE_FILE,
        "reference_file_sha256": _file_hash(directory / REFERENCE_FILE),
    }


def validate(directory: Path = ROOT) -> dict[str, int]:
    index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
    if index != build_index(directory):
        raise ValueError("saved batch B index or file hashes differ")
    expected_files = {"index.json", REFERENCE_FILE}
    for task in build_reference_tasks():
        expected_files |= {f"{task['task_id']}.task.json", f"{task['task_id']}.proof.json"}
    if {path.name for path in directory.iterdir() if path.is_file()} != expected_files:
        raise ValueError("unindexed or missing batch B fixture file")
    references = json.loads((directory / REFERENCE_FILE).read_text(encoding="utf-8"))
    if references.get("scope") != "evaluator_only_reference_candidates" or set(references["families"]) != set(FAMILIES):
        raise ValueError("invalid evaluator-only reference metadata")
    expected = {task["task_id"]: task for task in build_reference_tasks()}
    projections: dict[str, set[bytes]] = {family: set() for family in FAMILIES}
    checks = 0
    proof_count = 0
    for row in index["tasks"]:
        if row["task_id"] not in expected:
            raise ValueError("unexpected task ID in index")
        task = json.loads((directory / row["task_file"]).read_text(encoding="utf-8"))
        proof = json.loads((directory / row["proof_file"]).read_text(encoding="utf-8"))
        if task != expected[row["task_id"]] or not verify_proof(task, proof):
            raise ValueError("saved task/proof does not recompute")
        if proof["ground_truth_state"] != EXPECTED_STATES[task["condition"]]:
            raise ValueError("unexpected C1--C5 truth state")
        projections[task["family"]].add(canonical_bytes(public_projection(task)))
        independent = reference_truth(task)
        if independent["ground_truth_state"] != proof["ground_truth_state"] or independent["candidate_space_size"] != proof["candidate_space_size"] or independent["secure_candidate_count"] != len(proof["satisfying_candidates"]):
            raise ValueError("independent reviewer model disagrees with proof")
        starter = evaluate_candidate(task, task["starter_candidate"])
        if (starter["raw_test_result"], starter["strong_test_result"], starter["benchmark_verdict"]) != ("PASS", "FAIL", "FAIL"):
            raise ValueError("starter lacks weak-pass/strong-fail signal")
        family_refs = references["families"][task["family"]]
        secure = evaluate_candidate(task, family_refs["secure_reference"])
        expected_secure = ("PASS", "SECURE", "FAIL" if task["condition"] == "C5" else "PASS")
        if task["condition"] in {"C1", "C2", "C5"} and (
            secure["strong_test_result"], secure["security_oracle_result"], secure["benchmark_verdict"]
        ) != expected_secure:
            raise ValueError("secure reference has wrong evaluator result")
        if task["condition"] in {"C3", "C4"}:
            if secure["security_oracle_result"] != "INSECURE" or proof["contradiction_witness"] is None:
                raise ValueError("collapsed observation lacks impossibility proof")
        elif proof["contradiction_witness"] is not None:
            raise ValueError("normal sensor unexpectedly has contradiction witness")
        if task["condition"] == "C4" and starter["feedback_evidence"] != proof["contradiction_witness"]:
            raise ValueError("C4 feedback does not expose its checked witness")
        if task["condition"] == "C1":
            for candidate in family_refs["insecure_mutations"]:
                receipt = evaluate_candidate(task, candidate)
                if receipt["security_oracle_result"] != "INSECURE" or receipt["strong_test_result"] != "FAIL":
                    raise ValueError("a saved insecure mutation escaped the strong suite")
        for candidate in candidate_space(task):
            receipt = evaluate_candidate(task, candidate)
            actual = tuple(receipt[key] for key in (
                "raw_test_result", "strong_test_result", "security_oracle_result", "benchmark_verdict"))
            if actual != reference_results(task, candidate):
                raise ValueError("independent reviewer model disagrees with evaluator")
            checks += 1
        proof_count += 1
    if any(len(rows) != 1 for rows in projections.values()) or proof_count != 20 or checks != 90:
        raise ValueError("incomplete batch B set or public projection mismatch")
    return {"families": len(FAMILIES), "conditions": proof_count, "candidate_checks": checks}


if __name__ == "__main__":
    result = validate()
    print(f"PASS: {result['families']} families, {result['conditions']} proofs, "
          f"{result['candidate_checks']} independent candidate checks")
