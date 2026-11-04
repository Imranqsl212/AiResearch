"""Focused safeguards for source-bound excluded C5 candidate parity."""

from __future__ import annotations

import json
import unittest

from analysis import c5_first_submission_parity_20261104 as audit


class C5FirstSubmissionParityTests(unittest.TestCase):
    def test_saved_report_matches_archives_and_separate_denominators(self) -> None:
        report = audit.build_report()
        self.assertEqual(report, json.loads(audit.OUTPUT.read_text(encoding="utf-8")))
        self.assertFalse(report["eligible_for_main_analysis"])
        old = report["old_selected_persistent_veto"]["summary"]
        self.assertEqual(old["pairs"], 14)
        self.assertEqual(old["both_submitted_pairs"], 11)
        self.assertEqual(old["same_first_candidate_among_both"], 9)
        self.assertEqual(old["false_first_inspect_among_both"], 9)
        self.assertEqual(old["same_first_after_false_inspect_among_both"], 8)
        self.assertEqual(old["same_full_candidate_sequence_among_both"], 1)
        self.assertEqual(old["false_only_submission_pairs"], 3)
        self.assertEqual(old["same_first_oracle_secure"], 5)
        self.assertEqual(old["same_first_oracle_insecure"], 4)
        later = report["later_one_shot_cohorts_not_pooled"]
        self.assertEqual([(x["pairs"], x["both_submitted_pairs"],
                           x["same_first_candidate_among_both"]) for x in later],
                         [(3, 3, 2), (2, 2, 2), (4, 4, 1), (4, 2, 0)])
        self.assertEqual(later[-1]["false_only_submission_pairs"], 2)

    def test_same_hash_means_same_finite_result_in_old_pairs(self) -> None:
        report = json.loads(audit.OUTPUT.read_text(encoding="utf-8"))
        matched = [row for row in report["old_pairs"] if row["same_first_submission"]]
        self.assertEqual(len(matched), 9)
        for row in matched:
            arms = row["arms"]
            self.assertEqual(arms["TRUTHFUL_PASS"]["first_submission_raw"],
                             arms["FALSE_FAIL"]["first_submission_raw"])
            self.assertEqual(arms["TRUTHFUL_PASS"]["first_submission_oracle"],
                             arms["FALSE_FAIL"]["first_submission_oracle"])
            self.assertEqual(arms["TRUTHFUL_PASS"]["first_submission_raw"], "PASS")


if __name__ == "__main__":
    unittest.main()
