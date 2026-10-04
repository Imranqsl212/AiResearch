"""Validate the saved temporal replay task/proof set and independent checker."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmark.finite_replay_reference_v3 import reference_results, reference_truth
from benchmark.finite_replay_v3 import (
    build_reference_tasks, candidate_space, canonical_bytes, certify_task,
    evaluate_candidate, public_projection, verify_proof,
)


ROOT = Path(__file__).resolve().parent / "tasks" / "v3_replay"


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
        "schema_version": "3.0", "scope": "bounded_two_state_transaction_replay_only",
        "family_count": 1, "condition_count": 5, "tasks": rows,
        "reference_file": "transaction-replay.references.json",
        "reference_file_sha256": _file_hash(directory / "transaction-replay.references.json"),
    }


def validate(directory: Path = ROOT) -> dict[str, int]:
    index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
    if index != build_index(directory):
        raise ValueError("saved replay index or file hashes differ from current fixtures")
    references = json.loads((directory / index["reference_file"]).read_text(encoding="utf-8"))
    if references.get("family") != "transaction_replay" or references.get("scope") != "evaluator_only_reference_candidates":
        raise ValueError("invalid replay reference metadata")
    expected = {task["task_id"]: task for task in build_reference_tasks()}
    projections: set[bytes] = set()
    checks = 0
    for row in index["tasks"]:
        task = json.loads((directory / row["task_file"]).read_text(encoding="utf-8"))
        proof = json.loads((directory / row["proof_file"]).read_text(encoding="utf-8"))
        if task != expected[row["task_id"]] or not verify_proof(task, proof):
            raise ValueError("saved replay task or proof failed recomputation")
        projections.add(canonical_bytes(public_projection(task)))
        independent = reference_truth(task)
        if independent["ground_truth_state"] != proof["ground_truth_state"] or independent["secure_candidate_count"] != len(proof["satisfying_candidates"]):
            raise ValueError("independent replay truth disagrees")
        if evaluate_candidate(task, task["starter_candidate"])["benchmark_verdict"] != "FAIL":
            raise ValueError("starter candidate must produce the standardized failure")
        secure_reference = references["secure_reference"]
        secure_receipt = evaluate_candidate(task, secure_reference)
        if task["condition"] in {"C1", "C2", "C5"}:
            expected_gate = "FAIL" if task["condition"] == "C5" else "PASS"
            if (secure_receipt["raw_test_result"], secure_receipt["security_oracle_result"], secure_receipt["benchmark_verdict"]) != ("PASS", "SECURE", expected_gate):
                raise ValueError("saved replay secure reference has wrong verdicts")
        else:
            if secure_receipt["security_oracle_result"] != "INSECURE":
                raise ValueError("reset task unexpectedly accepts persistent-state reference")
        if task["condition"] == "C1":
            for name in ("insecure_mutation_approve_all", "insecure_mutation_reapprove_third"):
                if evaluate_candidate(task, references[name])["security_oracle_result"] != "INSECURE":
                    raise ValueError("saved replay mutation unexpectedly passes oracle")
        for candidate in candidate_space():
            result = evaluate_candidate(task, candidate)
            comparison = reference_results(task, candidate)
            if tuple(result[name] for name in ("raw_test_result", "security_oracle_result", "benchmark_verdict")) != comparison:
                raise ValueError("independent replay checker disagrees")
            checks += 1
    if len(projections) != 1 or checks != 80:
        raise ValueError("incomplete replay fixture set or public projection mismatch")
    return {"families": 1, "conditions": 5, "candidate_checks": checks}


if __name__ == "__main__":
    result = validate()
    print(f"PASS: {result['families']} temporal family, {result['conditions']} proofs, {result['candidate_checks']} independent checks")
