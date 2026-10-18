"""Offline contract and removed-capability tests; no model or Docker calls."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from benchmark.generate_real_code_candidate_v1 import DIRECTORY, generate, validate
from benchmark.real_code_candidate_v1 import (
    CONDITIONS, FAMILY_CONFIG, STATUS, WORLDS, build_contract,
    exercise_authored_reference, feedback_receipt, host_oracle,
    public_projection, unavailable_observation, unavailable_witness,
    validate_candidate,
)


class RealCodeCandidateV1Tests(unittest.TestCase):
    def test_saved_contracts_and_calibrations_are_exact(self) -> None:
        report = validate_candidate()
        self.assertEqual((report["family_count"], report["condition_count"]), (2, 10))
        self.assertEqual(report["status"], STATUS)
        self.assertFalse(report["main_ready"])
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(validate(DIRECTORY)["artifact_count"], 3)

    def test_actual_removed_argument_and_indistinguishable_worlds(self) -> None:
        for family in FAMILY_CONFIG:
            with self.subTest(family=family):
                left, right = WORLDS[family]
                self.assertEqual(unavailable_observation(family, left),
                                 unavailable_observation(family, right))
                self.assertNotEqual(host_oracle(family, left), host_oracle(family, right))
                witness = unavailable_witness(family)
                self.assertEqual(witness["required_outputs"],
                                 [host_oracle(family, left), host_oracle(family, right)])
                for world in (left, right):
                    available = exercise_authored_reference(family, world,
                                                            resource_present=True)
                    absent = exercise_authored_reference(family, world,
                                                         resource_present=False)
                    self.assertEqual(available["reference_output"], host_oracle(family, world))
                    self.assertFalse(available["resource_argument_is_none"])
                    self.assertIsNone(absent["reference_output"])
                    self.assertTrue(absent["resource_argument_is_none"])
                    self.assertIn(absent["reference_error_type"], {"AttributeError", "TypeError"})

    def test_truthful_feedback_and_c5_design_are_separate(self) -> None:
        for family in FAMILY_CONFIG:
            contract = build_contract(family)
            self.assertEqual(set(contract["conditions"]), set(CONDITIONS))
            self.assertEqual(contract["public_task"], public_projection(family))
            self.assertEqual(contract["status"], STATUS)
            self.assertNotIn("private_worlds", contract["public_task"])
            weak = feedback_receipt(family, "C3")
            detailed = feedback_receipt(family, "C4")
            self.assertEqual(weak["resource_present"], False)
            self.assertEqual(weak["observed_argument_value"], None)
            self.assertEqual(weak["evidence_scope"], "offline_authored_fixture_only")
            self.assertTrue(weak["offline_absence_probe"]["resource_argument_is_none"])
            self.assertNotIn("world_id", weak["offline_absence_probe"])
            self.assertNotIn("verifiable_witness", weak)
            self.assertEqual(detailed["verifiable_witness"], unavailable_witness(family))
            self.assertEqual(contract["conditions"]["C5"]["resource_present"], True)
            self.assertEqual(contract["conditions"]["C5"]["benchmark_gate"],
                             "false_fail_after_oracle_secure_onset")
            self.assertIsNone(contract["conditions"]["C5"]["unavailable_witness"])

    def test_write_once_artifacts_reject_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "candidate"
            self.assertEqual(generate(directory), generate(directory))
            index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
            index["contracts"][0]["contract_sha256"] = "0" * 64
            (directory / "index.json").write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact differs"):
                validate(directory)
            with self.assertRaisesRegex(ValueError, "versioned candidate artifact differs"):
                generate(directory)


if __name__ == "__main__":
    unittest.main()
