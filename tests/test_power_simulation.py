"""Math and provenance guards for precollection synthetic planning simulation."""

import math
import unittest

from analysis.power_simulation import (
    PlanningConfig,
    family_cluster_t_test,
    simulate_planning_power,
    student_t_critical_one_sided,
    student_t_survival,
)


class PowerSimulationTests(unittest.TestCase):
    def test_student_t_tails_match_closed_forms(self):
        # df=1 is Cauchy; df=2 has an elementary survival function.
        self.assertAlmostEqual(student_t_survival(1.0, 1), 0.25, places=12)
        self.assertAlmostEqual(student_t_survival(-1.0, 1), 0.75, places=12)
        self.assertAlmostEqual(student_t_survival(1.0, 2),
                               (1.0 - 1.0 / math.sqrt(3.0)) / 2.0, places=12)
        self.assertAlmostEqual(student_t_survival(0.0, 31), 0.5, places=12)
        self.assertAlmostEqual(student_t_critical_one_sided(31), 1.6955187825458569, places=9)

    def test_t_test_operates_on_families_and_fails_closed_when_degenerate(self):
        null = family_cluster_t_test([0.0, 1.0, 0.0, 1.0])
        self.assertEqual(null["n_families"], 4)
        self.assertAlmostEqual(null["estimate"], 0.5)
        self.assertAlmostEqual(null["one_sided_p_value"], 0.5)
        constant = family_cluster_t_test([1.0] * 32)
        self.assertIsNone(constant["one_sided_p_value"])
        self.assertIsNone(family_cluster_t_test([0.7])["one_sided_p_value"])

    def test_invalid_planning_assumptions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "no-exposure"):
            PlanningConfig(exposure_probability=0.5, incomplete_cell_probability=0.05)
        with self.assertRaisesRegex(ValueError, "probability bounds"):
            # Mean 0.01 with an unrealistically large ICC would imply q<0.
            from analysis.power_simulation import _latent_probability
            _latent_probability(0.01, 0.99, -1)

    def test_synthetic_report_is_deterministic_and_never_clears_real_study_gate(self):
        config = PlanningConfig(replicates=25, seed=9)
        first = simulate_planning_power(config)
        second = simulate_planning_power(config)
        self.assertEqual(first, second)
        self.assertEqual(len(first["scenarios"]), 9)
        self.assertFalse(first["preregistration_power_gate_cleared"])
        self.assertEqual(first["kind"], "precollection_synthetic_power_sensitivity_not_agent_data")
        self.assertTrue(all(row["replicates"] == 25 for row in first["scenarios"]))


if __name__ == "__main__":
    unittest.main()
