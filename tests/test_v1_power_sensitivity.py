"""Focused checks for the synthetic prospective C5 planning calculation."""

from __future__ import annotations

import unittest

from analysis.v1_power_sensitivity import Scenario, simulate


class C5PowerSensitivityTests(unittest.TestCase):
    def test_replay_is_deterministic_and_tracks_family_units(self) -> None:
        scenario = Scenario(families=20, onset_reach_probability=0.5,
                            false_fail_stop_reduction=0.2)
        first = simulate(scenario, replicates=40, seed=73)
        self.assertEqual(first, simulate(scenario, replicates=40, seed=73))
        self.assertLessEqual(first["mean_contributing_families"], 20)
        self.assertGreater(first["mean_valid_onset_pairs"], first["mean_contributing_families"])
        self.assertEqual(first["estimable_replicates"] + first["nonestimable_replicates"], 40)

    def test_onset_nonreach_is_nonestimable_not_zero_effect(self) -> None:
        scenario = Scenario(families=15, onset_reach_probability=0.13,
                            family_reach_shift=0.12)
        result = simulate(scenario, replicates=100, seed=12)
        self.assertGreater(result["nonestimable_replicates"], 0)
        self.assertLess(result["mean_contributing_families"], 15)

    def test_invalid_scenario_cannot_silently_clip_probabilities(self) -> None:
        with self.assertRaisesRegex(ValueError, "leave \\[0, 1\\]"):
            Scenario(false_fail_stop_reduction=0.8)
        with self.assertRaisesRegex(ValueError, "onset cap"):
            Scenario(max_onsets_per_family=11)


if __name__ == "__main__":
    unittest.main()
