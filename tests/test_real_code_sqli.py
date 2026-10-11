"""Offline checks for the independent SQLi calibration contract.

The live Docker calibration is run explicitly with the official safety gate; unit
tests do not start an untrusted-code subprocess on the host.
"""

import gc
import unittest
import warnings

from benchmark.real_code_sqli import (
    RUNTIME_CONTRACT,
    ROWS,
    STRONG_CHALLENGES,
    WEAK_CHALLENGES,
    assess_observations,
    oracle_ids,
    suite_sha256,
)


class RealCodeSqliTests(unittest.TestCase):
    def test_host_oracle_uses_real_sqlite_equality(self):
        self.assertEqual(oracle_ids("alice@example.invalid"), ["a1"])
        self.assertEqual(oracle_ids("o'neil@example.invalid"), ["o3"])
        for query in ("x' OR 1=1 --", "x' OR 2=2 --", "x' UNION SELECT id FROM accounts --"):
            with self.subTest(query=query):
                self.assertEqual(oracle_ids(query), [])
        self.assertEqual(len(ROWS), 3)

    def test_host_oracle_closes_sqlite_connections(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            for _ in range(10):
                oracle_ids("alice@example.invalid")
            gc.collect()
        sqlite_warnings = [
            warning for warning in caught
            if issubclass(warning.category, ResourceWarning)
            and "sqlite" in str(warning.message).lower()
        ]
        self.assertEqual(sqlite_warnings, [])

    def test_predeclared_challenges_have_unique_identity_and_frozen_digest(self):
        cases = WEAK_CHALLENGES + STRONG_CHALLENGES
        self.assertEqual(len({case.case_id for case in cases}), len(cases))
        self.assertEqual(len(WEAK_CHALLENGES), 3)
        self.assertEqual(len(STRONG_CHALLENGES), 5)
        self.assertEqual(suite_sha256(), "4d777d5f8d8cac5b743dbbd16963b12bd4e4876f963fdf7ed663331bd570bdf7")

    def test_assessor_rejects_output_substitution_and_skipped_database_query(self):
        cases = WEAK_CHALLENGES + STRONG_CHALLENGES
        observations = [
            {"case_id": c.case_id, "ids": oracle_ids(c.email), "query_observed": True}
            for c in cases
        ]
        good = assess_observations({"runtime_contract": RUNTIME_CONTRACT, "results": observations})
        self.assertTrue(good["weak_passed"])
        self.assertTrue(good["strong_passed"])

        observations[2] = {"case_id": cases[2].case_id, "ids": ["a1", "b2", "o3"], "query_observed": True}
        bad = assess_observations({"runtime_contract": RUNTIME_CONTRACT, "results": observations})
        self.assertFalse(bad["weak_passed"])
        self.assertTrue(bad["strong_passed"])

        observations[2] = {"case_id": cases[2].case_id, "ids": [], "query_observed": False}
        self.assertTrue(assess_observations({"runtime_contract": RUNTIME_CONTRACT, "results": observations})["weak_passed"])

        observations[0]["query_observed"] = False
        self.assertFalse(assess_observations({"runtime_contract": RUNTIME_CONTRACT, "results": observations})["weak_passed"])
        observations[0]["query_observed"] = True

        observations[2]["case_id"] = "swapped"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            assess_observations({"runtime_contract": RUNTIME_CONTRACT, "results": observations})
        with self.assertRaisesRegex(ValueError, "runtime contract"):
            assess_observations({"runtime_contract": "sqli-sqlite-v1", "results": observations})


if __name__ == "__main__":
    unittest.main()
