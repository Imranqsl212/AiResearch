"""Exhaustive test-set recount guards for the authored v7 task cards."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from analysis import v7_test_set_sufficiency_20261104 as audit


class TestSetSufficiencyTests(unittest.TestCase):
    def test_all_modes_and_nonempty_world_subsets_recount(self) -> None:
        report = audit.build_report()
        self.assertEqual(report, json.loads(audit.OUTPUT.read_text()))
        self.assertFalse(report["eligible_for_main_analysis"])
        self.assertEqual(report["task_count"], 24)
        self.assertEqual(report["candidate_mode_evaluations"], 78)
        self.assertEqual(report["raw_false_positive_mode_evaluations"], 26)
        by_task = {(r["family"], r["condition"]): r for r in report["rows"]}
        csrf = by_task["csrf_origin", "C1"]
        self.assertEqual(csrf["raw_false_positive_modes"], ["token_only", "origin_only"])
        self.assertEqual(csrf["minimal_sufficient_world_count"], 3)
        self.assertEqual(csrf["minimal_sufficient_sets"],
                         [["trusted_request", "cross_site_request", "missing_token"]])
        self.assertEqual(by_task["kdf_salt", "C1"]["minimal_sufficient_sets"],
                         [["principal_b"]])
        for row in report["rows"]:
            self.assertEqual(len(row["subsets"]), 2 ** row["world_count"] - 1)
            self.assertEqual(row["raw_false_negative_count"], 0)
            self.assertTrue(all(len(s) == row["minimal_sufficient_world_count"]
                                for s in row["minimal_sufficient_sets"]))

    def test_reference_disagreement_is_not_silently_counted(self) -> None:
        with patch.object(audit, "decision", return_value=False):
            with self.assertRaisesRegex(ValueError, "independent and local checker disagree"):
                audit.task_report("csrf_origin", "C1")


if __name__ == "__main__":
    unittest.main()
