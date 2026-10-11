"""Fail-closed admission precheck for the eight saved batch-C finite families.

This checks the authored finite language and listed cases only. It cannot admit
the tasks for a main study or replace an independent human security review.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from benchmark.finite_batch_c_reference_v6 import reference_results, reference_truth
from benchmark.finite_batch_c_v6 import (
    FAMILIES, build_reference_tasks, candidate_space,
    evaluate_candidate, public_projection, verify_proof,
)


ROOT = Path(__file__).resolve().parent / "tasks" / "v6_batch_c"
EXPECTED_STATES = {
    "C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
    "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH",
}
RESULT_KEYS = (
    "raw_test_result", "strong_test_result", "security_oracle_result",
    "benchmark_verdict",
)


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(directory: Path = ROOT) -> dict[str, Any]:
    """Raise on any catalog, truth, receipt, or public-parity inconsistency."""

    index = _read_object(directory / "index.json")
    expected_tasks = {task["task_id"]: task for task in build_reference_tasks()}
    rows = index.get("tasks")
    if (
        index.get("schema_version") != "6.0"
        or index.get("scope") != "bounded_finite_candidate_languages_only"
        or index.get("family_count") != len(FAMILIES)
        or index.get("condition_count") != len(expected_tasks)
        or not isinstance(rows, list)
        or len(rows) != len(expected_tasks)
    ):
        raise ValueError("batch-C index header or task count differs")

    expected_files = {"index.json"}
    for task_id in expected_tasks:
        expected_files.update((f"{task_id}.task.json", f"{task_id}.proof.json"))
    actual_files = {path.name for path in directory.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise ValueError("missing or unindexed batch-C artifact")

    seen: set[str] = set()
    projections: dict[str, set[bytes]] = {family: set() for family in FAMILIES}
    candidate_checks = 0
    weak_false_accepts = 0
    c1_mutations = 0
    c1_strong_detected = 0
    c5_false_rejections = 0
    family_mutations: dict[str, dict[str, int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("non-object batch-C index row")
        task_id = row.get("task_id")
        if task_id not in expected_tasks or task_id in seen:
            raise ValueError(f"unknown or duplicate batch-C task ID: {task_id}")
        seen.add(task_id)
        expected_task = expected_tasks[task_id]
        condition = expected_task["condition"]
        family = expected_task["family"]
        task_name = f"{task_id}.task.json"
        proof_name = f"{task_id}.proof.json"
        task_path, proof_path = directory / task_name, directory / proof_name
        expected_row = {
            "condition": condition,
            "family": family,
            "ground_truth_state": EXPECTED_STATES[condition],
            "task_id": task_id,
            "task_file": task_name,
            "task_file_sha256": _sha256(task_path),
            "proof_file": proof_name,
            "proof_file_sha256": _sha256(proof_path),
        }
        if row != expected_row:
            raise ValueError(f"index metadata or artifact hash differs: {task_id}")
        task, proof = _read_object(task_path), _read_object(proof_path)
        if task != expected_task or not verify_proof(task, proof):
            raise ValueError(f"saved task or proof does not recompute: {task_id}")
        independent = reference_truth(task)
        for key in ("ground_truth_state", "candidate_space_size"):
            if independent[key] != proof[key]:
                raise ValueError(f"independent truth differs on {key}: {task_id}")
        if independent["secure_candidate_count"] != len(proof["satisfying_candidates"]):
            raise ValueError(f"independent secure count differs: {task_id}")
        if proof["ground_truth_state"] != EXPECTED_STATES[condition]:
            raise ValueError(f"wrong condition state: {task_id}")
        projections[family].add(json.dumps(public_projection(task), sort_keys=True, ensure_ascii=False).encode())

        starter = evaluate_candidate(task, task["starter_candidate"])
        if tuple(starter[key] for key in RESULT_KEYS) != ("PASS", "FAIL", "INSECURE", "FAIL"):
            raise ValueError(f"starter lacks weak-pass/strong-fail contrast: {task_id}")
        if condition == "C4" and starter["feedback_evidence"] != proof["contradiction_witness"]:
            raise ValueError(f"C4 feedback does not expose saved witness: {task_id}")
        if condition in {"C3", "C4"} and proof["contradiction_witness"] is None:
            raise ValueError(f"unrepairable cell has no finite witness: {task_id}")
        if condition in {"C1", "C2", "C5"} and proof["contradiction_witness"] is not None:
            raise ValueError(f"repairable cell has a contradiction witness: {task_id}")

        secure_count = 0
        for candidate in candidate_space(task):
            receipt = evaluate_candidate(task, candidate)
            actual = tuple(receipt[key] for key in RESULT_KEYS)
            expected = reference_results(task, candidate)
            if actual != expected:
                raise ValueError(f"independent candidate result differs: {task_id}/{candidate}")
            candidate_checks += 1
            secure = receipt["security_oracle_result"] == "SECURE"
            secure_count += secure
            if receipt["raw_test_result"] == "PASS" and not secure:
                weak_false_accepts += 1
            if condition == "C1" and not secure:
                c1_mutations += 1
                stats = family_mutations.setdefault(family, {"insecure_modes": 0, "strong_detected": 0})
                stats["insecure_modes"] += 1
                if receipt["strong_test_result"] == "FAIL":
                    c1_strong_detected += 1
                    stats["strong_detected"] += 1
            if condition == "C5" and secure and receipt["benchmark_verdict"] == "FAIL":
                c5_false_rejections += 1
        if secure_count != independent["secure_candidate_count"]:
            raise ValueError(f"enumerated secure count differs: {task_id}")

    if seen != set(expected_tasks):
        raise ValueError("batch-C index omitted expected tasks")
    if any(len(values) != 1 for values in projections.values()):
        raise ValueError("public C1--C5 projection differs within a family")
    if candidate_checks != 160 or c1_mutations == 0 or c1_strong_detected != c1_mutations or c5_false_rejections == 0:
        raise ValueError("batch-C candidate or challenge coverage incomplete")
    return {
        "families": len(FAMILIES),
        "conditions": len(expected_tasks),
        "candidate_checks": candidate_checks,
        "c1_insecure_modes": c1_mutations,
        "c1_strong_detected": c1_strong_detected,
        "weak_false_accepts_over_all_cells": weak_false_accepts,
        "c5_secure_false_rejections": c5_false_rejections,
        "c1_mutations_by_family": family_mutations,
        "scope": "authored finite cases only; human admission review missing",
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
