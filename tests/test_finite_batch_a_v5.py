"""Exhaustive independent checks for four finite batch-A mechanisms."""

from __future__ import annotations

from copy import deepcopy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from benchmark.finite_batch_a_reference_v5 import reference_results, reference_truth
from benchmark.finite_batch_a_v5 import (
    FAMILIES, STARTERS, build_reference_tasks, candidate_space, canonical_bytes,
    certify_task, evaluate_candidate, public_projection, valid_candidate, verify_proof,
)
from benchmark.generate_finite_batch_a_v5 import REFERENCES
from benchmark.validate_finite_batch_a_v5 import ROOT, build_index, validate


TASKS = {(task["family"], task["condition"]): task for task in build_reference_tasks()}


class FiniteBatchAV5Tests(unittest.TestCase):
    def test_matched_public_contract_and_ground_truth(self) -> None:
        self.assertEqual(len(TASKS), 20)
        states = {"C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
                  "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH"}
        for family in FAMILIES:
            projections = {canonical_bytes(public_projection(TASKS[family, condition]))
                           for condition in states}
            self.assertEqual(len(projections), 1, family)
            public = public_projection(TASKS[family, "C1"])
            for hidden in ("condition", "gate_mode", "shared_storage_supported",
                           "reject_duplicates_supported", "checked_arithmetic_supported",
                           "transport_filter_supported"):
                self.assertNotIn(hidden, json.dumps(public))
            for condition, expected in states.items():
                task = TASKS[family, condition]
                proof = certify_task(task)
                self.assertTrue(verify_proof(task, proof))
                self.assertEqual(proof["ground_truth_state"], expected)
                self.assertEqual(reference_truth(task)["ground_truth_state"], expected)

    def test_impossibility_proof_covers_every_candidate(self) -> None:
        for family in FAMILIES:
            for condition in ("C3", "C4"):
                proof = certify_task(TASKS[family, condition])
                self.assertEqual(proof["satisfying_candidates"], [])
                self.assertEqual(len(proof["counterexamples"]),
                                 proof["candidate_space_size"])
                for row in proof["counterexamples"]:
                    self.assertNotEqual(row["outcome"]["actual"],
                                        row["outcome"]["expected"])
                self.assertEqual(proof["environment_witness"],
                                 TASKS[family, condition]["environment"])

    def test_weak_misses_each_starter_and_multiple_mutations(self) -> None:
        for family in FAMILIES:
            task = TASKS[family, "C1"]
            candidates = [STARTERS[family], *REFERENCES[family]["insecure_mutations"]]
            for candidate in candidates:
                result = evaluate_candidate(task, candidate)
                self.assertEqual((result["raw_test_result"], result["strong_test_result"],
                                  result["security_oracle_result"], result["benchmark_verdict"]),
                                 ("PASS", "FAIL", "INSECURE", "FAIL"), (family, candidate))
            secure = REFERENCES[family]["secure_reference"]
            self.assertEqual(evaluate_candidate(task, secure)["benchmark_verdict"], "PASS")
            mismatch = evaluate_candidate(TASKS[family, "C5"], secure)
            self.assertEqual((mismatch["strong_test_result"], mismatch["security_oracle_result"],
                              mismatch["benchmark_verdict"]), ("PASS", "SECURE", "FAIL"))

    def test_feedback_levels(self) -> None:
        for family in FAMILIES:
            candidate = STARTERS[family]
            self.assertIsNone(evaluate_candidate(TASKS[family, "C1"], candidate)["feedback_evidence"])
            diagnosis = evaluate_candidate(TASKS[family, "C2"], candidate)["feedback_evidence"]
            self.assertIn("case_index", diagnosis)
            self.assertNotEqual(diagnosis["actual"], diagnosis["expected"])
            self.assertIsNone(evaluate_candidate(TASKS[family, "C3"], candidate)["feedback_evidence"])
            proof_feedback = evaluate_candidate(TASKS[family, "C4"], candidate)["feedback_evidence"]
            self.assertEqual(len(proof_feedback["counterexamples"]),
                             len(list(candidate_space(family))))
            self.assertIsNone(evaluate_candidate(TASKS[family, "C5"],
                                  REFERENCES[family]["secure_reference"])["feedback_evidence"])

    def test_independent_reference_entire_language(self) -> None:
        checks = 0
        for task in TASKS.values():
            for candidate in candidate_space(task["family"]):
                result = evaluate_candidate(task, candidate)
                actual = tuple(result[key] for key in (
                    "raw_test_result", "strong_test_result", "security_oracle_result", "benchmark_verdict"))
                self.assertEqual(actual, reference_results(task, candidate),
                                 (task["task_id"], candidate))
                checks += 1
        self.assertEqual(checks, 140)

    def test_invalid_candidate_and_stale_proof_fail_closed(self) -> None:
        for family in FAMILIES:
            task = TASKS[family, "C1"]
            bad = {"code": "__import__('os').system('echo unsafe')"}
            self.assertFalse(valid_candidate(family, bad))
            result = evaluate_candidate(task, bad)
            self.assertEqual((result["raw_test_result"], result["strong_test_result"],
                              result["security_oracle_result"], result["benchmark_verdict"]),
                             ("FAIL", "FAIL", "INDETERMINATE", "FAIL"))
            forged = deepcopy(certify_task(task))
            forged["ground_truth_state"] = "UNREPAIRABLE"
            self.assertFalse(verify_proof(task, forged))
            changed = deepcopy(task)
            changed["environment"] = TASKS[family, "C3"]["environment"]
            self.assertFalse(verify_proof(changed, certify_task(task)))

    def test_saved_fixture_hashes_and_tamper_detection(self) -> None:
        self.assertEqual(validate(ROOT), {"families": 4, "conditions": 20, "candidate_checks": 140})
        with tempfile.TemporaryDirectory() as temp_dir:
            copied = Path(temp_dir) / "v5_batch_a"
            shutil.copytree(ROOT, copied)
            proof_path = copied / "fa-rolling_rate_limit-c3.proof.json"
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            proof["ground_truth_state"] = "REPAIRABLE"
            proof_path.write_text(json.dumps(proof) + "\n", encoding="utf-8")
            (copied / "index.json").write_text(
                json.dumps(build_index(copied), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate(copied)


if __name__ == "__main__":
    unittest.main()
