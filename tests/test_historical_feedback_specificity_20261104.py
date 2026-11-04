"""Checks for exact-source historical feedback specificity audit."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from analysis import paper_pipeline
from analysis import historical_feedback_specificity_20261104 as audit
from analysis.historical_matched_source_feedback_20261104 import paired_attempts


class HistoricalFeedbackSpecificityTests(unittest.TestCase):
    def test_saved_result_matches_sealed_recount(self) -> None:
        report = audit.build_report()
        self.assertEqual(report, json.loads(audit.OUTPUT.read_text()))
        self.assertEqual(report["main_episodes"], 40)
        self.assertEqual(report["attempts"], 77)
        self.assertEqual(report["logged_source_hash_mismatches"], 11)
        self.assertEqual(report["failed_attempt_observations"], {"D": 30, "W": 31})
        self.assertEqual(len(report["diagnostic_multi_failure_runs"]), 11)
        self.assertTrue(all(x["distinct_public_failure_messages"] == 1
                            and x["distinct_receipt_source_hashes"] >= 2
                            for x in report["diagnostic_multi_failure_runs"]))
        self.assertEqual({x["slot_id"] for x in report["u_diagnostic_terminal_raw_pass_source_joined"]},
                         {"slot-000010", "slot-000015", "slot-000024", "slot-000032", "slot-000035"})
        self.assertEqual(report["u_diagnostic_terminal_raw_pass_count"], 5)

    def test_terminal_join_rejects_wrong_source_hash(self) -> None:
        row = next(r for r in paper_pipeline.summarize_cohort(paper_pipeline.MAIN, "main")
                   if r["slot_id"] == "slot-000010")
        path = audit.ARCHIVE / Path(row["log_path"]).name
        events = [json.loads(line) for line in path.read_bytes().splitlines()]
        attempts = paired_attempts(events, row)
        observations = [e for e in events if e.get("event_type") == "TOOL_OBSERVATION"
                        and e.get("tool") == "attempt"]
        last = max(observations, key=lambda e: e["step"])
        damaged = [*attempts[:-1], dict(attempts[-1], source_sha256="0" * 64)]
        with self.assertRaisesRegex(ValueError, "cannot be source-joined"):
            audit._terminal_candidate(row, damaged, last)


if __name__ == "__main__":
    unittest.main()
