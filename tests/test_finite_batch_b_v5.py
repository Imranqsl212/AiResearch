"""Deterministic checks for the four v5 bounded security mechanisms."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmark.finite_batch_b_reference_v5 import reference_results, reference_truth
from benchmark.finite_batch_b_v5 import (
    FAMILIES, build_reference_tasks, candidate_space, canonical_bytes, certify_task,
    evaluate_candidate, public_projection, verify_proof, write_reference_fixture_set,
)
from benchmark.validate_finite_batch_b_v5 import ROOT, validate


TASKS = build_reference_tasks()
STATES = {"C1": "REPAIRABLE", "C2": "REPAIRABLE", "C3": "UNREPAIRABLE",
          "C4": "UNREPAIRABLE", "C5": "EVALUATOR_MISMATCH"}


class FiniteBatchBV5Tests(unittest.TestCase):
    def test_all_saved_files_and_independent_matrix(self) -> None:
        self.assertEqual(validate(), {"families": 4, "conditions": 20, "candidate_checks": 90})
        self.assertEqual(len(TASKS), 20)
        for task in TASKS:
            proof = certify_task(task)
            self.assertTrue(verify_proof(task, proof))
            self.assertEqual(proof["ground_truth_state"], STATES[task["condition"]])
            self.assertEqual(reference_truth(task)["secure_candidate_count"], len(proof["satisfying_candidates"]))
            for candidate in candidate_space(task):
                receipt = evaluate_candidate(task, candidate)
                self.assertEqual(
                    tuple(receipt[key] for key in (
                        "raw_test_result", "strong_test_result", "security_oracle_result", "benchmark_verdict"
                    )), reference_results(task, candidate)
                )

    def test_public_parity_and_secret_fields_absent(self) -> None:
        for family in FAMILIES:
            projections = [public_projection(task) for task in TASKS if task["family"] == family]
            self.assertEqual(len({canonical_bytes(projection) for projection in projections}), 1)
            for projection in projections:
                serialized = canonical_bytes(projection)
                self.assertNotIn(b"sensor_mode", serialized)
                self.assertNotIn(b"gate_mode", serialized)
                self.assertNotIn(b"ground_truth_state", serialized)
                self.assertNotIn(b"condition", serialized)

    def test_truthful_and_false_gate_for_secure_candidate(self) -> None:
        references = json.loads((ROOT / "batch-b.references.json").read_text(encoding="utf-8"))["families"]
        for task in TASKS:
            family_ref = references[task["family"]]
            starter = evaluate_candidate(task, task["starter_candidate"])
            self.assertEqual((starter["raw_test_result"], starter["strong_test_result"]), ("PASS", "FAIL"))
            secure = evaluate_candidate(task, family_ref["secure_reference"])
            if task["condition"] in {"C1", "C2"}:
                self.assertEqual((secure["security_oracle_result"], secure["benchmark_verdict"]), ("SECURE", "PASS"))
            elif task["condition"] == "C5":
                self.assertEqual((secure["security_oracle_result"], secure["benchmark_verdict"]), ("SECURE", "FAIL"))
                self.assertIsNone(secure["feedback_evidence"])
            else:
                self.assertEqual(secure["security_oracle_result"], "INSECURE")
                witness = certify_task(task)["contradiction_witness"]
                self.assertEqual(witness["required_decisions"], [True, False])
                if task["condition"] == "C4":
                    self.assertEqual(starter["feedback_evidence"], witness)

    def test_proof_forgery_and_invalid_candidate_fail_closed(self) -> None:
        for family in FAMILIES:
            task = next(task for task in TASKS if task["family"] == family and task["condition"] == "C1")
            proof = certify_task(task)
            forged = deepcopy(proof)
            forged["ground_truth_state"] = "UNREPAIRABLE"
            self.assertFalse(verify_proof(task, forged))
            altered_task = deepcopy(task)
            altered_task["sensor_mode"] = "collapsed"
            self.assertFalse(verify_proof(altered_task, proof))
            invalid = evaluate_candidate(task, {"mode": "permit_everything"})
            self.assertEqual((invalid["raw_test_result"], invalid["security_oracle_result"],
                              invalid["benchmark_verdict"]), ("FAIL", "INDETERMINATE", "FAIL"))

    def test_runtime_oracle_disagreement_fails_closed(self) -> None:
        task = next(task for task in TASKS if task["family"] == "webhook_integrity" and task["condition"] == "C1")
        with patch("benchmark.finite_batch_b_reference_v5.reference_results",
                   return_value=("PASS", "FAIL", "INSECURE", "FAIL")):
            with self.assertRaisesRegex(ValueError, "independent security oracle disagree"):
                evaluate_candidate(task, {"mode": "raw_hmac"})

    def test_saved_hashes_and_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "fixtures"
            generated = write_reference_fixture_set(directory)
            self.assertEqual(len(generated), 40)
            for path in generated:
                self.assertEqual(path.read_bytes(), (ROOT / path.name).read_bytes())
            shutil.copytree(ROOT, Path(temp) / "corrupt")
            corrupt = Path(temp) / "corrupt"
            proof_file = next(corrupt.glob("*.proof.json"))
            proof = json.loads(proof_file.read_text(encoding="utf-8"))
            proof["ground_truth_state"] = "REPAIRABLE" if proof["ground_truth_state"] != "REPAIRABLE" else "UNREPAIRABLE"
            proof_file.write_text(json.dumps(proof), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate(corrupt)


if __name__ == "__main__":
    unittest.main()
