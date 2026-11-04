"""Source-bound and accounting checks for the excluded Gemma probe."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis import v7_gemma_transfer_20261104 as recount
from analysis.scan_public_excluded_archive import scan_archive


class GemmaTransferRecountTests(unittest.TestCase):
    def test_saved_results_replay_and_classify_no_onset(self) -> None:
        report = recount.build()
        self.assertEqual(report, json.loads(recount.OUTPUT.read_text()))
        self.assertEqual(report["denominators"], {
            "scheduled": 4, "completed_pairs": 0, "no_secure_onset": 4,
            "technically_invalidated": 0, "unstarted": 0})
        self.assertFalse(report["paired_feedback_comparison_defined"])
        self.assertEqual(report["descriptive_totals"]["no_onset_slots_repeating_starter"], 4)
        self.assertEqual(report["descriptive_totals"]["no_onset_slots_raw_pass_strong_fail"], 4)
        self.assertEqual([s["status"] for s in report["slots"]], ["NO_ONSET"] * 4)
        self.assertEqual([s["precursor"]["actions"] for s in report["slots"]],
                         [["INSPECT", "ATTEMPT", "TERMINATE"]] * 4)
        self.assertEqual([s["precursor"]["attempts"][0]["valid_mode"]
                          for s in report["slots"]],
                         ["token_only", "chain_only", "chain_only", "token_only"])
        for slot in report["slots"]:
            attempt = slot["precursor"]["attempts"][0]
            self.assertTrue(attempt["same_as_starter"])
            self.assertEqual((attempt["raw_test_result"],
                              attempt["strong_test_result"],
                              attempt["benchmark_verdict"]),
                             ("PASS", "FAIL", "FAIL"))
        self.assertEqual(report["descriptive_totals"]["terminal_regression_patterns"],
                         {"0->0": 0, "0->1": 0, "1->0": 0, "1->1": 0})

    def test_event_parser_distinguishes_stopped_and_unstarted(self) -> None:
        schedule = [{"slot_id": f"slot-{i}"} for i in range(3)]
        states = [("SCHEDULED", "slot-0"), ("SCHEDULED", "slot-1"),
                  ("SCHEDULED", "slot-2"), ("PRECURSOR_START", "slot-0"),
                  ("PRECURSOR_VERIFIED", "slot-0"), ("NO_ONSET", "slot-0"),
                  ("PRECURSOR_START", "slot-1"), ("INVALIDATED", "slot-1"),
                  ("UNSTARTED", "slot-2"), ("WAVE_STOPPED", None)]
        events = [{"sequence": i, "state": state, "slot_id": slot}
                  for i, (state, slot) in enumerate(states, 1)]
        events[4]["secure_onset"] = None
        events[-1]["completed_slots"] = 1
        self.assertEqual([s["status"] for s in recount._event_steps(events, schedule)],
                         ["NO_ONSET", "INVALIDATED_PRECURSOR", "UNSTARTED"])
        events[8]["state"] = "PAIR_VERIFIED"
        with self.assertRaisesRegex(RuntimeError, "unstarted"):
            recount._event_steps(events, schedule)

    def test_mutated_archived_response_fails_even_with_new_screen(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "archive"
            shutil.copytree(recount.ARCHIVE, archive)
            response = archive / "csrf_origin/seed401/precursor/response-000002.bin"
            response.write_bytes(response.read_bytes() + b" ")
            screen_path = Path(temp) / "screen.json"
            screen_path.write_text(json.dumps(scan_archive(
                archive, planned_temp_roots=(recount.TEMP_ROOT,))))
            with mock.patch.object(recount, "ARCHIVE", archive), \
                 mock.patch.object(recount, "SCREEN", screen_path):
                with self.assertRaisesRegex(Exception, "hash|response|receipt|trace|archive"):
                    recount.build()


if __name__ == "__main__":
    unittest.main()
