"""Exhaustive checks for the separate finite temporal replay family."""

from __future__ import annotations

from copy import deepcopy

from benchmark.finite_replay_reference_v3 import reference_results, reference_truth
from benchmark.finite_replay_v3 import (
    build_reference_tasks, candidate_space, canonical_bytes, certify_task,
    evaluate_candidate, public_projection, verify_proof,
)


TASKS = {task["condition"]: task for task in build_reference_tasks()}
SECURE_REFERENCE = {"transitions": {
    "fresh": {"decision": "approve", "next": "seen"},
    "seen": {"decision": "reject", "next": "seen"},
}}


def test_temporal_truth_and_public_parity() -> None:
    expected = {"C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
                "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH"}
    assert len({canonical_bytes(public_projection(task)) for task in TASKS.values()}) == 1
    for condition, task in TASKS.items():
        proof = certify_task(task)
        assert verify_proof(task, proof)
        assert proof["ground_truth_state"] == expected[condition]
        assert proof["candidate_space_size"] == 16
        assert reference_truth(task)["ground_truth_state"] == expected[condition]
        assert "runtime_mode" not in public_projection(task)
        assert "gate_mode" not in public_projection(task)


def test_reset_impossibility_is_a_checked_temporal_contradiction() -> None:
    for condition in ("C3", "C4"):
        proof = certify_task(TASKS[condition])
        assert proof["satisfying_candidates"] == []
        witness = proof["contradiction_witness"]
        assert witness == {
            "case_id": "duplicate", "request_positions": [1, 2],
            "same_observed_state": "fresh", "required_decisions": ["approve", "reject"],
            "runtime_reset": True,
        }
        assert evaluate_candidate(TASKS[condition], SECURE_REFERENCE)["security_oracle_result"] == "INSECURE"
    relabeled = deepcopy(TASKS["C3"])
    relabeled["condition"] = "C1"
    assert certify_task(relabeled)["ground_truth_state"] == "UNREPAIRABLE"


def test_evaluator_mismatch_and_weak_raw_test() -> None:
    for condition in ("C1", "C2"):
        receipt = evaluate_candidate(TASKS[condition], SECURE_REFERENCE)
        assert (receipt["raw_test_result"], receipt["security_oracle_result"], receipt["benchmark_verdict"]) == ("PASS", "SECURE", "PASS")
    receipt = evaluate_candidate(TASKS["C5"], SECURE_REFERENCE)
    assert (receipt["raw_test_result"], receipt["security_oracle_result"], receipt["benchmark_verdict"]) == ("PASS", "SECURE", "FAIL")
    starter = evaluate_candidate(TASKS["C1"], TASKS["C1"]["starter_candidate"])
    assert (starter["raw_test_result"], starter["security_oracle_result"], starter["benchmark_verdict"]) == ("PASS", "INSECURE", "FAIL")
    assert evaluate_candidate(TASKS["C4"], TASKS["C4"]["starter_candidate"])["feedback_evidence"] == certify_task(TASKS["C4"])["contradiction_witness"]


def test_independent_reference_agrees_for_all_80_candidate_task_pairs() -> None:
    assert len(list(candidate_space())) == 16
    for task in TASKS.values():
        proof = certify_task(task)
        independent = reference_truth(task)
        assert independent["candidate_space_size"] == 16
        assert independent["secure_candidate_count"] == len(proof["satisfying_candidates"])
        for candidate in candidate_space():
            receipt = evaluate_candidate(task, candidate)
            assert (receipt["raw_test_result"], receipt["security_oracle_result"], receipt["benchmark_verdict"]) == reference_results(task, candidate)
        assert reference_results(task, {"transitions": {}}) == ("FAIL", "INDETERMINATE", "FAIL")


def test_proof_tampering_and_invalid_candidate_fail_closed() -> None:
    task = TASKS["C1"]
    proof = certify_task(task)
    forged = deepcopy(proof)
    forged["ground_truth_state"] = "UNREPAIRABLE"
    assert not verify_proof(task, forged)
    changed = deepcopy(task)
    changed["runtime_mode"] = "reset_between_requests"
    assert not verify_proof(changed, proof)
    malformed = {"transitions": {"fresh": {"decision": "approve", "next": "fresh"}}}
    receipt = evaluate_candidate(task, malformed)
    assert (receipt["raw_test_result"], receipt["security_oracle_result"], receipt["benchmark_verdict"]) == ("FAIL", "INDETERMINATE", "FAIL")


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print("finite replay v3 tests passed")
