"""Offline checks for the versioned C3/C4 feedback correction."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from benchmark.generate_real_code_candidate_v1 import (
    DIRECTORY as PREVIOUS_DIRECTORY, validate as validate_previous,
)
from benchmark.generate_real_code_candidate_v1_1 import (
    DIRECTORY, generate, validate,
)
from benchmark.real_code_candidate_v1 import (
    FAMILY_CONFIG, WORLDS, exercise_authored_reference, unavailable_witness,
)
from benchmark.real_code_candidate_v1_1 import (
    GENERIC_FAILURE, SUPERSEDED_INDEX_SHA256, VERSION, build_contract,
    feedback_receipt, public_projection, validate_candidate,
)


class RealCodeCandidateV11Tests(unittest.TestCase):
    def test_old_artifacts_remain_exact_and_new_index_is_versioned(self) -> None:
        self.assertEqual(validate_previous(PREVIOUS_DIRECTORY)["index_sha256"],
                         SUPERSEDED_INDEX_SHA256)
        report = validate(DIRECTORY)
        self.assertEqual((report["family_count"], report["condition_count"]), (2, 10))
        self.assertEqual(report["schema_version"], VERSION)
        self.assertEqual(report["supersedes_index_sha256"], SUPERSEDED_INDEX_SHA256)
        self.assertFalse(report["main_ready"])
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(validate_candidate()["c3_feedback"], "GENERIC_TRUTHFUL_FAILURE")

    def test_c3_is_exactly_generic_and_c4_exposes_bounded_certificate(self) -> None:
        for family in FAMILY_CONFIG:
            with self.subTest(family=family):
                c1 = feedback_receipt(family, "C1")
                c3 = feedback_receipt(family, "C3")
                c4 = feedback_receipt(family, "C4")
                self.assertEqual(c1, GENERIC_FAILURE)
                self.assertEqual(c3, c1)
                self.assertEqual(set(c3), {"kind", "status", "message"})
                self.assertNotIn("resource", json.dumps(c3).lower())
                self.assertNotIn("absent", json.dumps(c3).lower())
                self.assertEqual(c4["status"], "RESOURCE_ABSENT")
                self.assertEqual(c4["certificate_scope"], "offline_authored_fixture_only")
                self.assertEqual(c4["verifiable_witness"], unavailable_witness(family))
                self.assertTrue(c4["offline_absence_probe"]["resource_argument_is_none"])
                contract = build_contract(family)
                self.assertEqual(contract["public_task"], public_projection(family))
                self.assertEqual(contract["conditions"]["C3"]["feedback"],
                                 "generic_truthful_failure_no_absence_disclosure")
                self.assertEqual(contract["conditions"]["C4"]["feedback"],
                                 "verified_bounded_impossibility_certificate")
                self.assertIsNone(contract["conditions"]["C3"]["candidate_argument_when_absent"])

    def test_absent_capability_remains_real_in_both_hidden_worlds(self) -> None:
        for family, worlds in WORLDS.items():
            for world in worlds:
                call = exercise_authored_reference(family, world, resource_present=False)
                self.assertFalse(call["resource_present"])
                self.assertTrue(call["resource_argument_is_none"])
                self.assertIsNone(call["reference_output"])

    def test_new_artifacts_are_write_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "candidate-v1-1"
            self.assertEqual(generate(directory), generate(directory))
            contract = directory / "sqlite_lookup.contract.json"
            contract.write_bytes(contract.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "artifact differs"):
                validate(directory)
            with self.assertRaisesRegex(ValueError, "versioned v1.1 artifact differs"):
                generate(directory)


if __name__ == "__main__":
    unittest.main()
