from __future__ import annotations

import unittest

from experiments.run_rag_overnight_profile import (
    MAIN_FAMILIES,
    PILOT_FAMILIES,
    build_profile_tasks,
    validate_profile,
)


class RagOvernightProfileTests(unittest.TestCase):
    def test_profile_is_balanced_and_disjoint(self) -> None:
        report = validate_profile()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["pilot_arms"], 8)
        self.assertEqual(report["main_arms"], 40)

    def test_every_family_has_full_condition_and_retrieval_blocks(self) -> None:
        for families in (PILOT_FAMILIES, MAIN_FAMILIES):
            rows = build_profile_tasks(families)
            for family in families:
                block = [row for row in rows if row["family"] == family]
                self.assertEqual(len(block), 8)
                self.assertEqual({row["condition"] for row in block}, {"RD", "UD", "RW", "UW"})
                self.assertEqual({row["retrieval_mode"] for row in block}, {"off", "relevant"})


if __name__ == "__main__":
    unittest.main()
