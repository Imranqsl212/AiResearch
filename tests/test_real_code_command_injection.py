"""Offline contract tests; untrusted source is never run on the host."""

import unittest

from benchmark.real_code_command_injection import (
    RUNTIME_CONTRACT,
    STRONG_CHALLENGES,
    WEAK_CHALLENGES,
    assess_observations,
    oracle_output,
    suite_sha256,
)


class RealCodeCommandInjectionTests(unittest.TestCase):
    def test_frozen_challenges_and_oracle(self):
        cases = WEAK_CHALLENGES + STRONG_CHALLENGES
        self.assertEqual(len(cases), 8)
        self.assertEqual(len({c.case_id for c in cases}), 8)
        self.assertEqual(oracle_output("alpha"), "Alpha report\n")
        self.assertEqual(oracle_output("alpha; printf X > ../marker"), None)
        self.assertEqual(
            suite_sha256(),
            "0c71e60047134ad4b961be3dfb0f0df7f1301c6f319a17c107ec746e3350d8b0",
        )

    def test_assessor_rejects_side_effect_and_shape_substitution(self):
        cases = WEAK_CHALLENGES + STRONG_CHALLENGES
        observations = [
            {"case_id": case.case_id, "value": oracle_output(case.filename), "marker_created": False}
            for case in cases
        ]
        report = assess_observations({"runtime_contract": RUNTIME_CONTRACT, "results": observations})
        self.assertTrue(report["weak_passed"])
        self.assertTrue(report["strong_passed"])

        observations[2]["marker_created"] = True
        report = assess_observations({"runtime_contract": RUNTIME_CONTRACT, "results": observations})
        self.assertFalse(report["weak_passed"])
        self.assertTrue(report["strong_passed"])
        observations[2]["marker_created"] = False

        observations[3]["value"] = "forged"
        self.assertFalse(assess_observations({"runtime_contract": RUNTIME_CONTRACT, "results": observations})["strong_passed"])
        observations[3]["case_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            assess_observations({"runtime_contract": RUNTIME_CONTRACT, "results": observations})
        with self.assertRaisesRegex(ValueError, "runtime contract"):
            assess_observations({"runtime_contract": "wrong", "results": observations})


if __name__ == "__main__":
    unittest.main()
