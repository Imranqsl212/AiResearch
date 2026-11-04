"""Guard the per-world interpretation of the two stopped temp-0.3 waves."""

import json
import unittest

from analysis import v7_temp03_error_direction_20261104 as direction


class Temp03ErrorDirectionTest(unittest.TestCase):
    def test_saved_recount_and_separate_denominators(self) -> None:
        result = direction.build()
        self.assertEqual(result, json.loads(direction.OUTPUT.read_text()))
        self.assertEqual([row["summary"]["scheduled_precursors"]
                          for row in result["cohorts"]], [32, 32])
        self.assertEqual([row["summary"]["verified_pairs"]
                          for row in result["cohorts"]], [4, 4])
        self.assertEqual([row["summary"]["not_run_after_stop"]
                          for row in result["cohorts"]], [24, 22])

    def test_terminal_regressions_are_false_denials_not_csrf_acceptance(self) -> None:
        cohorts = direction.build()["cohorts"]
        self.assertEqual([row["summary"]["false_only_regression_pairs"]
                          for row in cohorts], [3, 3])
        for cohort in cohorts:
            for arm in ("TRUTHFUL_PASS", "FALSE_FAIL"):
                self.assertEqual(cohort["summary"]["terminal_error_kinds"][arm]
                                 ["false_accept_only"], 0)
                self.assertEqual(cohort["summary"]["terminal_error_kinds"][arm]
                                 ["both"], 0)
                for pair in cohort["pairs"]:
                    self.assertEqual(pair["arms"][arm]["terminal"]["false_accepts"], [])


if __name__ == "__main__":
    unittest.main()
