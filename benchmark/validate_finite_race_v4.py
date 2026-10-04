"""Validate frozen counter-race task/proof/reference files independently."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmark.finite_race_reference_v4 import reference_results, reference_truth
from benchmark.finite_race_v4 import (
    build_reference_tasks, candidate_space, canonical_bytes, certify_task,
    evaluate_candidate, public_projection, verify_proof,
)


ROOT = Path(__file__).resolve().parent / "tasks" / "v4_race"
REFERENCE_FILE = "counter-race.references.json"


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
        "schema_version": "4.0", "scope": "bounded_two_request_counter_updates_only",
        "family_count": 1, "condition_count": 5, "tasks": rows,
        "reference_file": REFERENCE_FILE,
        "reference_file_sha256": _file_hash(directory / REFERENCE_FILE),
    }


def validate(directory: Path = ROOT) -> dict[str, int]:
    index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
    if index != build_index(directory):
        raise ValueError("saved race index or file hashes differ from current fixtures")
    expected_files = {"index.json", REFERENCE_FILE}
    for task in build_reference_tasks():
        expected_files |= {f"{task['task_id']}.task.json", f"{task['task_id']}.proof.json"}
    if {path.name for path in directory.iterdir() if path.is_file()} != expected_files:
        raise ValueError("unindexed or missing race fixture file")
    references = json.loads((directory / REFERENCE_FILE).read_text(encoding="utf-8"))
    if references.get("family") != "counter_race" or references.get("scope") != "evaluator_only_reference_candidates":
        raise ValueError("invalid race reference metadata")
    expected = {task["task_id"]: task for task in build_reference_tasks()}
    projections: set[bytes] = set()
    checks = 0
    for row in index["tasks"]:
        task = json.loads((directory / row["task_file"]).read_text(encoding="utf-8"))
        proof = json.loads((directory / row["proof_file"]).read_text(encoding="utf-8"))
        if task != expected[row["task_id"]] or not verify_proof(task, proof):
            raise ValueError("saved race task or proof failed recomputation")
        projections.add(canonical_bytes(public_projection(task)))
        independent = reference_truth(task)
        if independent["ground_truth_state"] != proof["ground_truth_state"] or independent["secure_candidate_count"] != len(proof["satisfying_candidates"]):
            raise ValueError("independent race truth disagrees")
        starter = evaluate_candidate(task, task["starter_candidate"])
        if starter["benchmark_verdict"] != "FAIL" or starter["raw_test_result"] != "PASS":
            raise ValueError("race starter must produce the standardized weak-pass/gate-fail signal")
        secure = evaluate_candidate(task, references["secure_reference"])
        if task["condition"] in {"C1", "C2", "C5"}:
            gate = "FAIL" if task["condition"] == "C5" else "PASS"
            if (secure["strong_test_result"], secure["security_oracle_result"], secure["benchmark_verdict"]) != ("PASS", "SECURE", gate):
                raise ValueError("saved race secure reference has wrong verdicts")
        elif secure["security_oracle_result"] != "INSECURE":
            raise ValueError("race C3/C4 unexpectedly accepts reference")
        if task["condition"] == "C1":
            for name in ("insecure_mutation_request_mutex", "insecure_mutation_nonatomic"):
                mutation = evaluate_candidate(task, references[name])
                if (mutation["raw_test_result"], mutation["strong_test_result"], mutation["security_oracle_result"]) != ("PASS", "FAIL", "INSECURE"):
                    raise ValueError("saved race mutation unexpectedly passes strong oracle")
        for candidate in candidate_space():
            receipt = evaluate_candidate(task, candidate)
            actual = tuple(receipt[key] for key in (
                "raw_test_result", "strong_test_result", "security_oracle_result", "benchmark_verdict"))
            if actual != reference_results(task, candidate):
                raise ValueError("independent race checker disagrees")
            checks += 1
    if len(projections) != 1 or checks != 30:
        raise ValueError("incomplete race fixture set or public projection mismatch")
    return {"families": 1, "conditions": 5, "candidate_checks": checks}


if __name__ == "__main__":
    result = validate()
    print(f"PASS: {result['families']} race family, {result['conditions']} proofs, {result['candidate_checks']} independent checks")
