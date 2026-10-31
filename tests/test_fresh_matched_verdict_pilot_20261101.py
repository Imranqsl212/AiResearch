"""Focused integrity and outcome checks for the fresh one-shot pilot recount."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from analysis import fresh_matched_verdict_pilot_20261101 as pilot


class FreshMatchedVerdictPilotTests(unittest.TestCase):
    def test_verified_recount_matches_saved_json_and_preserves_all_scheduled_slots(self) -> None:
        report = pilot.build_report()
        self.assertEqual(report, json.loads(pilot.OUTPUT.read_text(encoding="utf-8")))
        fresh = report["fresh_schedule"]
        self.assertEqual((fresh["scheduled_precursors"], fresh["secure_onsets"], fresh["verified_pairs"]), (4, 3, 3))
        self.assertEqual(fresh["no_onset_families"], ["tls_hostname"])
        self.assertIsNone(fresh["slots"][3]["pair"])
        self.assertEqual(fresh["slots"][3]["pair_status"], "NOT_RUN_NO_ONSET")
        self.assertEqual(
            [(slot["family"], slot["pair"]["arms"]["FALSE_FAIL"]["terminal_finite_property_regression"])
             for slot in fresh["slots"] if slot["pair"]],
            [("csrf_origin", 1), ("environment_injection", 0), ("nonce_uniqueness", 0)],
        )

    def test_archived_repeat_is_not_counted_as_fresh_and_csrf_trajectories_duplicate(self) -> None:
        report = pilot.build_report()
        comparisons = report["old_selected_onset_repeat"]["same_action_and_candidate_hash_sequences"]
        self.assertEqual(len(report["fresh_schedule"]["slots"]), 4)
        self.assertEqual(len(comparisons), 3)
        for arm_match in comparisons.values():
            self.assertEqual(arm_match, {"TRUTHFUL_PASS": True, "FALSE_FAIL": True})
        old_precursor = report["old_selected_onset_repeat"]["original_precursor"]
        self.assertEqual(old_precursor["first_secure_submission_decision"], 3)
        self.assertIn("seed41", old_precursor["archive_dir"])

    def test_wrong_branch_seed_and_modified_archived_decision_fail_closed(self) -> None:
        source = pilot.ARCHIVE / "csrf_origin/pair"
        precursor = pilot.ARCHIVE / "csrf_origin/precursor"
        with self.assertRaisesRegex(RuntimeError, "branch seed changed"):
            pilot._pair(source, precursor, 999)
        with tempfile.TemporaryDirectory(dir=pilot.ROOT, prefix="fresh-pair-integrity-") as temp:
            copy = Path(temp) / "pair"
            shutil.copytree(source, copy)
            decision = copy / "false_fail.000001.decision.json"
            data = json.loads(decision.read_text(encoding="utf-8"))
            data["action"] = "TERMINATE"
            decision.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(Exception):
                pilot._pair(copy, precursor, 310)


if __name__ == "__main__":
    unittest.main()
