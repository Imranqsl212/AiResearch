"""Source-bound checks for the excluded finite-checker deletion experiment."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from analysis import v7_leave_one_world_out_20261104 as audit


class LeaveOneWorldOutTests(unittest.TestCase):
    def test_all_eight_families_have_single_case_sensitivity(self) -> None:
        result = audit.build_report()
        self.assertEqual(result, json.loads(audit.OUTPUT.read_text()))
        self.assertFalse(result["eligible_for_main_analysis"])
        self.assertEqual(result["family_count"], 8)
        self.assertEqual(result["omission_count_per_condition"], 23)
        self.assertEqual(result["c1_omissions_admitting_insecure_modes"], 16)
        self.assertEqual(result["c1_newly_accepted_failure_kinds"],
                         {"unsafe_accept": 8, "denial_only": 7, "wrong_output": 1})
        self.assertEqual(result["c3_omissions_making_task_feasible"], 15)
        self.assertEqual(result["c3_no_contradiction_but_no_mode"], 1)
        self.assertEqual(result["families_with_c1_false_acceptance"], 8)
        self.assertEqual(result["families_with_c3_new_feasibility"], 8)
        cases = {(row["family"], row["omitted_case_id"]): row for row in result["omissions"]}
        self.assertEqual(cases["csrf_origin", "cross_site_request"]["C1"]["newly_accepted_modes"],
                         ["token_only"])
        self.assertEqual(cases["kdf_salt", "principal_b"]["C1"]["newly_accepted_modes"],
                         ["fixed_salt"])
        self.assertFalse(cases["kdf_salt", "principal_a"]["C3"]["contradiction_witness_remains"])
        self.assertEqual(cases["kdf_salt", "principal_a"]["C3"]["accepted_modes"], [])

    def test_reference_disagreement_fails_closed(self) -> None:
        task, _ = audit._task("csrf_origin", "C1")
        with patch.object(audit, "decision", return_value=True):
            with self.assertRaisesRegex(ValueError, "independent reference"):
                audit._accepted_modes(task)


if __name__ == "__main__":
    unittest.main()
