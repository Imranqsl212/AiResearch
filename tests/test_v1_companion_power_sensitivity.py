"""Targeted validation of companion family-level Holm simulation."""

from __future__ import annotations

import unittest

from analysis.v1_companion_power_sensitivity import Scenario, _holm, simulate


class CompanionPowerSensitivityTests(unittest.TestCase):
    def test_holm_stops_at_first_failed_threshold(self) -> None:
        self.assertEqual(_holm((0.01, 0.024, 0.06)), (True, True, False))
        self.assertEqual(_holm((0.02, 0.021, 0.03)), (False, False, False))

    def test_replay_and_cluster_count(self) -> None:
        case = Scenario(families=20, technical_run_loss=0.05)
        result = simulate(case, replicates=25, seed=17)
        self.assertEqual(result, simulate(case, replicates=25, seed=17))
        for count in result["mean_contributing_families"].values():
            self.assertLessEqual(count, 20)
        self.assertLessEqual(result["probability_all_three_holm_rejections"],
                             result["probability_any_holm_rejection"])

    def test_invalid_probability_fails_instead_of_clipping(self) -> None:
        with self.assertRaisesRegex(ValueError, "leave \\[0, 1\\]"):
            Scenario(diagnostic_effect=0.5, rag_effect=0.3)


if __name__ == "__main__":
    unittest.main()
