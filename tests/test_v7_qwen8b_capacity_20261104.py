"""Source-bound recount and missingness guards for the excluded Qwen3:8b probe."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis import v7_qwen8b_capacity_20261104 as recount
from analysis.scan_public_excluded_archive import scan_archive


class Qwen8bCapacityRecountTests(unittest.TestCase):
    def test_saved_results_replay_all_scheduled_slots(self) -> None:
        report = recount.build()
        self.assertEqual(report, json.loads(recount.OUTPUT.read_text()))
        d = report["denominators"]
        self.assertEqual(d["scheduled"], 4)
        self.assertEqual(sum(d[key] for key in (
            "completed_pairs", "no_secure_onset", "technically_invalidated",
            "unstarted")), 4)
        self.assertEqual(len(report["slots"]), 4)
        self.assertEqual(report["paired_feedback_comparison_defined"],
                         d["completed_pairs"] > 0)
        self.assertEqual(report["eligible_for_main_analysis"], False)
        self.assertEqual(d, {"scheduled": 4, "completed_pairs": 0,
                             "no_secure_onset": 0, "technically_invalidated": 1,
                             "unstarted": 3})
        self.assertEqual([s["status"] for s in report["slots"]],
                         ["INVALIDATED_PRECURSOR"] + ["UNSTARTED"] * 3)
        technical = report["slots"][0]["technical"]
        self.assertEqual(technical["error_type"], "ExcludedOllamaTransportTimeout")
        self.assertEqual(technical["model_dispatch_attempts"], 1)
        self.assertEqual(technical["response_count"], 0)
        self.assertEqual(technical["decision_count"], 0)
        self.assertEqual(technical["request_timeout_seconds"], 300)
        self.assertTrue(technical["unanswered_final_request"])

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

    def test_mutated_archived_request_fails_even_with_new_screen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "archive"
            shutil.copytree(recount.ARCHIVE, archive)
            request = archive / "csrf_origin/seed501/precursor/request-000001.bin"
            request.write_bytes(request.read_bytes() + b" ")
            screen_path = Path(temporary) / "screen.json"
            screen_path.write_text(json.dumps(scan_archive(
                archive, planned_temp_roots=(recount.TEMP_ROOT,))))
            with mock.patch.object(recount, "ARCHIVE", archive), \
                 mock.patch.object(recount, "SCREEN", screen_path):
                with self.assertRaisesRegex(Exception, "hash|request|receipt|trace|archive"):
                    recount.build()


if __name__ == "__main__":
    unittest.main()
