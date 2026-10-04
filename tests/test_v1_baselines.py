"""Baseline treatment separation at matched retry budgets."""

import unittest

from agent.v1_baselines import BASELINES, baseline_for, prompt_for


class BaselineDefinitionsTest(unittest.TestCase):
    def test_all_six_baselines_defined(self) -> None:
        self.assertEqual(set(BASELINES), {"B0", "B1", "B2", "B3", "B4", "B5"})
        self.assertEqual(BASELINES["B0"].max_generated_attempts, 1)
        self.assertEqual({BASELINES[name].max_generated_attempts for name in ("B1", "B2", "B3", "B4", "B5")}, {4})

    def test_invalid_evidence_and_retrieval_pairs_rejected(self) -> None:
        with self.assertRaises(ValueError):
            baseline_for("B4", condition="C1", retrieval_mode="R0")
        with self.assertRaises(ValueError):
            baseline_for("B5", condition="C1", retrieval_mode="R0")
        with self.assertRaises(ValueError):
            baseline_for("B1", condition="C1", retrieval_mode="R1")
        with self.assertRaises(ValueError):
            baseline_for("B3", condition="C1", retrieval_mode="R1")
        self.assertEqual(baseline_for("B4", condition="C4", retrieval_mode="R0").name, "evidence_aware")
        self.assertEqual(BASELINES["B3"].retry_instruction, BASELINES["B5"].retry_instruction)

    def test_single_shot_has_no_retry(self) -> None:
        with self.assertRaises(ValueError):
            prompt_for(BASELINES["B0"], failure_number=2)


if __name__ == "__main__":
    unittest.main()
