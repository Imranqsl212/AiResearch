"""Semantic checks for the proposed v7 batch-C replacement only."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark.finite_batch_c_reference_v7 import reference_results, reference_truth, reference_witness
from benchmark.finite_batch_c_v7 import (
    FAMILIES, build_reference_tasks, candidate_space, certify_task, decision,
    evaluate_candidate, observe, public_projection,
)
from benchmark.generate_finite_batch_c_v7 import generate
from benchmark.validate_finite_batch_c_v7 import ROOT, validate


class SemanticBatchC7Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = build_reference_tasks()
        cls.by_key = {(task["family"], task["condition"]): task for task in cls.tasks}

    def test_exhaustive_oracle_parity_and_condition_states(self):
        self.assertEqual(len(self.tasks), 40)
        expected = {"C1": "REPAIRABLE", "C2": "REPAIRABLE",
                    "C3": "UNREPAIRABLE", "C4": "UNREPAIRABLE",
                    "C5": "EVALUATOR_MISMATCH"}
        checks = 0
        for task in self.tasks:
            proof = certify_task(task)
            truth = reference_truth(task)
            self.assertEqual(proof["ground_truth_state"], expected[task["condition"]])
            self.assertEqual(proof["ground_truth_state"], truth["ground_truth_state"])
            self.assertEqual(len(proof["satisfying_candidates"]), truth["secure_candidate_count"])
            self.assertEqual(proof["contradiction_witness"], reference_witness(task))
            for candidate in candidate_space(task):
                receipt = evaluate_candidate(task, candidate)
                self.assertEqual(tuple(receipt[key] for key in (
                    "raw_test_result", "strong_test_result",
                    "security_oracle_result", "benchmark_verdict")),
                    reference_results(task, candidate))
                checks += 1
        self.assertEqual(checks, 130)

    def test_indistinguishable_worlds_have_conflicting_required_outputs(self):
        for family in FAMILIES:
            for condition in ("C3", "C4"):
                task = self.by_key[(family, condition)]
                witness = reference_witness(task)
                self.assertIsNotNone(witness)
                left, right = witness["world_facts"]
                self.assertEqual(observe(task, left), observe(task, right))
                self.assertNotEqual(left["required_output"], right["required_output"])
                self.assertEqual(witness["required_outputs"],
                                 [left["required_output"], right["required_output"]])
                # Any deterministic stateless candidate must output the same
                # action on the two identical observations.
                for candidate in candidate_space(task):
                    self.assertEqual(decision(task, candidate, left),
                                     decision(task, candidate, right))
                feedback = evaluate_candidate(task, task["starter_candidate"])["feedback_evidence"]
                self.assertEqual(feedback, witness if condition == "C4" else None)

    def test_public_parity_and_weak_strong_gate_examples(self):
        for family in FAMILIES:
            projections = [public_projection(self.by_key[(family, c)]) for c in
                           ("C1", "C2", "C3", "C4", "C5")]
            self.assertTrue(all(p == projections[0] for p in projections))
            self.assertTrue(projections[0]["candidate_language"]["stateless"])
            self.assertEqual(set(projections[0]["candidate_language"]["mode_semantics"]),
                             set(FAMILIES[family]["modes"]))
            c1 = self.by_key[(family, "C1")]
            starter = evaluate_candidate(c1, c1["starter_candidate"])
            self.assertEqual((starter["raw_test_result"], starter["strong_test_result"]),
                             ("PASS", "FAIL"))
            c5 = self.by_key[(family, "C5")]
            secure = certify_task(c5)["satisfying_candidates"][0]
            receipt = evaluate_candidate(c5, secure)
            self.assertEqual((receipt["security_oracle_result"], receipt["benchmark_verdict"]),
                             ("SECURE", "FAIL"))

    def test_reference_rejects_forged_requirement_and_observation_leak(self):
        for family in FAMILIES:
            task = copy.deepcopy(self.by_key[(family, "C3")])
            old = task["worlds"][1]["required_output"]
            task["worlds"][1]["required_output"] = not old if type(old) is bool else "salt:forged"
            with self.assertRaises(ValueError):
                reference_truth(task)
            with self.assertRaises(ValueError):
                certify_task(task)

        task = self.by_key[("csrf_origin", "C3")]
        original_observe = observe

        def leak_origin(changed_task, world):
            view = original_observe(changed_task, world)
            view["origin"] = world["origin"]
            return view

        with patch("benchmark.finite_batch_c_v7.observe", side_effect=leak_origin):
            with self.assertRaisesRegex(ValueError, "independent oracle disagree"):
                evaluate_candidate(task, {"mode": "token_and_origin"})

    def test_generator_write_once_and_index_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "v7"
            first = generate(directory)
            second = generate(directory)
            self.assertEqual(first, second)
            self.assertEqual(first["files"], 81)
            self.assertEqual(validate(directory)["candidate_checks"], 130)
            index_path = directory / "index.json"
            content = json.loads(index_path.read_text())
            content["tasks"][0]["proof_file_sha256"] = "0" * 64
            index_path.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, "metadata or digest"):
                validate(directory)
            with self.assertRaisesRegex(ValueError, "versioned v7 artifact differs"):
                generate(directory)

    def test_checked_in_candidate_has_stable_hash_and_is_not_admitted(self):
        report = validate(ROOT)
        self.assertEqual(report["status"], "STRUCTURAL_PRE_REVIEW_ONLY_NOT_HUMAN_ADMITTED")
        self.assertEqual(report["index_sha256"],
                         "f8fac1b0171152237f2736493b286ef7cca1e853fa1880915a7c2484817c54d1")
        self.assertEqual(report["c4_world_fact_witnesses"], 8)


if __name__ == "__main__":
    unittest.main()
