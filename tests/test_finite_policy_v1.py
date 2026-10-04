"""Validity checks for the finite policy research fixture."""

from __future__ import annotations

from copy import deepcopy
from itertools import product

from benchmark.finite_policy_reference import reference_results, reference_truth
from benchmark.finite_policy_v1 import (
    build_reference_tasks,
    canonical_bytes,
    certify_task,
    evaluate_candidate,
    public_projection,
    sha256,
    verify_proof,
)


TASKS = {task["condition"]: task for task in build_reference_tasks()}
SECURE_REFERENCE = {"decisions": {
    "role=guest;session=active": "deny",
    "role=owner;session=active": "allow",
    "role=owner;session=expired": "deny",
}}


def test_exhaustive_ground_truth_and_matched_public_projection() -> None:
    assert {condition: certify_task(task)["ground_truth_state"] for condition, task in TASKS.items()} == {
        "C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
        "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH",
    }
    assert len({canonical_bytes(public_projection(task)) for task in TASKS.values()}) == 1
    for task in TASKS.values():
        public = public_projection(task)
        assert public["environment"]["domain"] == "web"
        assert all(name not in public for name in ("condition", "gate_mode", "states", "raw_test_state_ids", "ground_truth_state"))
        proof = certify_task(task)
        assert proof["candidate_space_size"] == 8
        assert verify_proof(task, proof)


def test_unrepairability_is_a_contradiction_not_a_condition_flag() -> None:
    for condition in ("C3", "C4"):
        task = TASKS[condition]
        proof = certify_task(task)
        assert proof["satisfying_candidates"] == []
        witness = proof["contradiction_witness"]
        assert witness["observation_key"] == "role=owner;session=active"
        assert set(witness["required_decisions"]) == {"allow", "deny"}
        assert len(witness["state_ids"]) == 2
        receipt = evaluate_candidate(task, SECURE_REFERENCE)
        assert receipt["raw_test_result"] == "PASS"
        assert receipt["security_oracle_result"] == "INSECURE"
        assert receipt["benchmark_verdict"] == "FAIL"
    relabeled = deepcopy(TASKS["C3"])
    relabeled["condition"] = "C1"
    assert certify_task(relabeled)["ground_truth_state"] == "UNREPAIRABLE"


def test_repairable_and_evaluator_mismatch_are_distinct() -> None:
    for condition in ("C1", "C2"):
        receipt = evaluate_candidate(TASKS[condition], SECURE_REFERENCE)
        assert (receipt["raw_test_result"], receipt["security_oracle_result"], receipt["benchmark_verdict"]) == ("PASS", "SECURE", "PASS")
    mismatch = evaluate_candidate(TASKS["C5"], SECURE_REFERENCE)
    assert (mismatch["raw_test_result"], mismatch["security_oracle_result"], mismatch["benchmark_verdict"]) == ("PASS", "SECURE", "FAIL")
    assert mismatch["feedback"] == "SECURITY CHECK FAILED."
    assert certify_task(TASKS["C5"])["secure_candidate_gate_verdict"] == "FAIL"


def test_feedback_semantics_and_starter_mutations() -> None:
    assert evaluate_candidate(TASKS["C1"], TASKS["C1"]["starter_candidate"])["feedback"] == "SECURITY CHECK FAILED."
    diagnostic = evaluate_candidate(TASKS["C2"], TASKS["C2"]["starter_candidate"])
    assert diagnostic["feedback_evidence"] == {"observation_key": "role=guest;session=active", "required_decision": "deny"}
    for condition in ("C3", "C5"):
        assert evaluate_candidate(TASKS[condition], TASKS[condition]["starter_candidate"])["feedback"] == "SECURITY CHECK FAILED."
    impossibility = evaluate_candidate(TASKS["C4"], TASKS["C4"]["starter_candidate"])
    assert impossibility["feedback_evidence"] == certify_task(TASKS["C4"])["contradiction_witness"]
    assert "contradictory decisions" in impossibility["feedback"]
    deny_all = {"decisions": {key: "deny" for key in SECURE_REFERENCE["decisions"]}}
    for candidate in (TASKS["C1"]["starter_candidate"], deny_all):
        receipt = evaluate_candidate(TASKS["C1"], candidate)
        assert receipt["security_oracle_result"] == "INSECURE"
        assert receipt["benchmark_verdict"] == "FAIL"


def test_malformed_policy_and_proof_tampering_fail_closed() -> None:
    task = TASKS["C1"]
    malformed = {"decisions": {"role=owner;session=active": "allow"}}
    result = evaluate_candidate(task, malformed)
    assert (result["raw_test_result"], result["security_oracle_result"], result["benchmark_verdict"]) == ("FAIL", "INDETERMINATE", "FAIL")
    assert result["candidate_hash"] == sha256(malformed)
    proof = certify_task(task)
    forged = deepcopy(proof)
    forged["ground_truth_state"] = "UNREPAIRABLE"
    assert not verify_proof(task, forged)
    altered_task = deepcopy(task)
    altered_task["states"][0]["facts"]["authorized"] = False
    assert not verify_proof(altered_task, proof)
    malformed_task = deepcopy(task)
    malformed_task["states"][0]["facts"]["authorized"] = "true"
    assert not verify_proof(malformed_task, proof)
    try:
        certify_task(malformed_task)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed task did not fail closed")


def test_independent_reference_checker_agrees_for_every_finite_candidate() -> None:
    for task in TASKS.values():
        proof = certify_task(task)
        alternate = reference_truth(task)
        assert proof["ground_truth_state"] == alternate["ground_truth_state"]
        assert proof["candidate_space_size"] == alternate["candidate_space_size"] == 8
        assert len(proof["satisfying_candidates"]) == alternate["secure_candidate_count"]
        if proof["contradiction_witness"]:
            assert proof["contradiction_witness"]["state_ids"] == alternate["contradiction_state_ids"]
        keys = proof["observation_keys"]
        for assignment in product(("allow", "deny"), repeat=len(keys)):
            candidate = {"decisions": dict(zip(keys, assignment))}
            actual = evaluate_candidate(task, candidate)
            independent = reference_results(task, candidate)
            assert (actual["raw_test_result"], actual["security_oracle_result"], actual["benchmark_verdict"]) == independent
    assert reference_results(TASKS["C1"], {"decisions": {}}) == ("FAIL", "INDETERMINATE", "FAIL")


def test_insecure_mutations_are_detected_and_raw_test_limit_is_explicit() -> None:
    allow_all = TASKS["C1"]["starter_candidate"]
    deny_all = {"decisions": {key: "deny" for key in SECURE_REFERENCE["decisions"]}}
    for mutation in (allow_all, deny_all):
        result = evaluate_candidate(TASKS["C1"], mutation)
        assert result["security_oracle_result"] == "INSECURE"
        assert result["benchmark_verdict"] == "FAIL"
    # C3/C4 hide a fourth state from the finite raw tests. This is an intentional
    # raw-test false acceptance, which the exhaustive security oracle detects.
    for condition in ("C3", "C4"):
        result = evaluate_candidate(TASKS[condition], SECURE_REFERENCE)
        assert result["raw_test_result"] == "PASS"
        assert result["security_oracle_result"] == "INSECURE"


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print("finite-policy v1 tests passed")
