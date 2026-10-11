"""Fail-closed structural and semantic pre-review of batch-C v7 artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from benchmark.finite_batch_c_reference_v7 import reference_results, reference_truth, reference_witness
from benchmark.finite_batch_c_v7 import (
    FAMILIES, build_reference_tasks, candidate_space, certify_task,
    decision, evaluate_candidate, observe, public_projection, verify_proof,
)

ROOT = Path(__file__).resolve().parent / "tasks" / "v7_batch_c"
RESULT_KEYS = ("raw_test_result", "strong_test_result", "security_oracle_result", "benchmark_verdict")
STATES = {"C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
          "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH"}


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(directory: Path = ROOT) -> dict[str, Any]:
    expected = {task["task_id"]: task for task in build_reference_tasks()}
    index = _read_object(directory / "index.json")
    rows = index.get("tasks")
    if (set(index) != {"schema_version", "scope", "status", "family_count", "condition_count", "tasks"}
            or index["schema_version"] != "7.0"
            or index["scope"] != "bounded_stateless_modes_and_explicit_finite_worlds_only"
            or index["status"] != "PROPOSED_NOT_HUMAN_ADMITTED"
            or index["family_count"] != 8 or index["condition_count"] != 40
            or not isinstance(rows, list) or len(rows) != 40):
        raise ValueError("batch-C v7 index header differs")
    expected_files = {"index.json"}
    for task_id in expected:
        expected_files.update({f"{task_id}.task.json", f"{task_id}.proof.json"})
    if {p.name for p in directory.iterdir() if p.is_file()} != expected_files:
        raise ValueError("batch-C v7 artifact set differs")

    seen: set[str] = set()
    projections: dict[str, set[bytes]] = {family: set() for family in FAMILIES}
    candidate_checks = 0
    weak_false_accepts = 0
    c1_nonconforming = 0
    c1_unsafe_accept = 0
    c1_denial_only = 0
    c1_wrong_output = 0
    c5_secure_false_rejections = 0
    c4_world_fact_witnesses = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("task_id") not in expected or row["task_id"] in seen:
            raise ValueError("duplicate or unknown v7 index row")
        task_id = row["task_id"]
        seen.add(task_id)
        authored = expected[task_id]
        condition, family = authored["condition"], authored["family"]
        task_name, proof_name = f"{task_id}.task.json", f"{task_id}.proof.json"
        task_path, proof_path = directory / task_name, directory / proof_name
        if row != {
            "task_id": task_id, "family": family, "condition": condition,
            "ground_truth_state": STATES[condition],
            "task_file": task_name, "task_file_sha256": _sha(task_path),
            "proof_file": proof_name, "proof_file_sha256": _sha(proof_path),
        }:
            raise ValueError(f"v7 index metadata or digest differs: {task_id}")
        task, proof = _read_object(task_path), _read_object(proof_path)
        if task != authored or not verify_proof(task, proof) or proof != certify_task(task):
            raise ValueError(f"v7 task/proof differs from authored semantics: {task_id}")
        truth = reference_truth(task)
        witness = reference_witness(task)
        if (proof["ground_truth_state"] != truth["ground_truth_state"]
                or proof["ground_truth_state"] != STATES[condition]
                or proof["candidate_space_size"] != truth["candidate_space_size"]
                or len(proof["satisfying_candidates"]) != truth["secure_candidate_count"]
                or proof["contradiction_witness"] != witness):
            raise ValueError(f"v7 independent reference differs: {task_id}")
        if condition in {"C3", "C4"}:
            if witness is None or len(witness["world_facts"]) != 2:
                raise ValueError(f"v7 unrepairability lacks world-fact witness: {task_id}")
            left, right = witness["world_facts"]
            if (observe(task, left) != observe(task, right)
                    or left["required_output"] == right["required_output"]
                    or witness["required_outputs"] != [left["required_output"], right["required_output"]]):
                raise ValueError(f"v7 contradiction does not follow from worlds: {task_id}")
        elif witness is not None:
            raise ValueError(f"v7 repairable task has contradiction: {task_id}")
        projections[family].add(json.dumps(public_projection(task), sort_keys=True,
                                           ensure_ascii=False).encode("utf-8"))
        starter = evaluate_candidate(task, task["starter_candidate"])
        if tuple(starter[k] for k in RESULT_KEYS) != ("PASS", "FAIL", "INSECURE", "FAIL"):
            raise ValueError(f"v7 starter lacks weak-pass/strong-fail contrast: {task_id}")
        if condition == "C2" and not (starter["feedback_evidence"] and
                                      starter["feedback_evidence"]["actual_output"] !=
                                      starter["feedback_evidence"]["required_output"]):
            raise ValueError(f"v7 C2 feedback lacks a failing case: {task_id}")
        if condition == "C4":
            if starter["feedback_evidence"] != witness:
                raise ValueError(f"v7 C4 feedback lacks contradiction: {task_id}")
            c4_world_fact_witnesses += 1
        elif condition != "C2" and starter["feedback_evidence"] is not None:
            raise ValueError(f"v7 evidence leaked in condition {condition}: {task_id}")

        for candidate in candidate_space(task):
            receipt = evaluate_candidate(task, candidate)
            actual = tuple(receipt[k] for k in RESULT_KEYS)
            if actual != reference_results(task, candidate):
                raise ValueError(f"v7 candidate/reference mismatch: {task_id}/{candidate}")
            candidate_checks += 1
            secure = receipt["security_oracle_result"] == "SECURE"
            weak_false_accepts += receipt["raw_test_result"] == "PASS" and not secure
            if condition == "C1" and not secure:
                c1_nonconforming += 1
                failures = [(world["required_output"], decision(task, candidate, world))
                            for world in task["worlds"]
                            if decision(task, candidate, world) != world["required_output"]]
                unsafe_accept = any(required is False and actual is True
                                    for required, actual in failures)
                denial = any(required is True and actual is False
                             for required, actual in failures)
                if unsafe_accept:
                    c1_unsafe_accept += 1
                elif denial:
                    c1_denial_only += 1
                else:
                    c1_wrong_output += 1
                if receipt["strong_test_result"] != "FAIL":
                    raise ValueError(f"v7 strong test missed nonconforming mode: {task_id}/{candidate}")
            if condition == "C5" and secure and receipt["benchmark_verdict"] == "FAIL":
                c5_secure_false_rejections += 1
        if reference_results(task, {"mode": "nonexistent"}) != ("FAIL", "FAIL", "INDETERMINATE", "FAIL"):
            raise ValueError(f"v7 invalid candidate was not rejected: {task_id}")

    if (seen != set(expected) or any(len(p) != 1 for p in projections.values())
            or candidate_checks != 130 or c1_nonconforming != 18
            or (c1_unsafe_accept, c1_denial_only, c1_wrong_output) != (8, 7, 3)
            or weak_false_accepts < 40 or c5_secure_false_rejections != 8
            or c4_world_fact_witnesses != 8):
        raise ValueError("v7 coverage or public parity incomplete")
    return {
        "status": "STRUCTURAL_PRE_REVIEW_ONLY_NOT_HUMAN_ADMITTED",
        "families": 8, "tasks": 40, "candidate_checks": candidate_checks,
        "c1_nonconforming_modes_detected": c1_nonconforming,
        "c1_unsafe_accept_modes": c1_unsafe_accept,
        "c1_denial_only_modes": c1_denial_only,
        "c1_wrong_output_modes": c1_wrong_output,
        "weak_false_accepts_over_all_cells": weak_false_accepts,
        "c4_world_fact_witnesses": c4_world_fact_witnesses,
        "c5_secure_false_rejections": c5_secure_false_rejections,
        "index_sha256": _sha(directory / "index.json"),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
