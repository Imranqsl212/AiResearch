"""Evidence and integrity guards for the historical terminate-latency recount."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from analysis import historical_terminate_latency_20261104 as audit


class HistoricalTerminateLatencyTests(unittest.TestCase):
    def test_sealed_recount_has_expected_action_and_time_boundaries(self) -> None:
        report = audit.build_report()
        self.assertEqual(report["sealed_episodes"], 40)
        self.assertEqual(report["episodes_with_acknowledged_terminate"], 14)
        self.assertEqual(report["terminate_tool_calls"], 15)
        self.assertEqual(report["later_logged_attempt_calls"], 0)
        self.assertEqual(report["self_labeled_acknowledgement_to_stop_seconds"]["median"],
                         128.44624)
        self.assertEqual([c["slot_id"] for c in report["cases"]
                          if c["stop_event"] == "TIMEOUT"], ["slot-000022"])
        self.assertEqual([c["slot_id"] for c in report["cases"]
                          if c["later_logged_tool_calls"]], ["slot-000033"])
        svg = audit.render_svg(report).decode()
        self.assertEqual(svg.count('slot 0000'), 14)
        self.assertIn('0.002 · TIMEOUT', svg)
        self.assertNotIn('parameters.source', svg)

    def test_log_mutation_is_rejected_before_a_result_can_change(self) -> None:
        original = Path.read_bytes

        def corrupted(path: Path) -> bytes:
            data = original(path)
            if path.name.endswith("slot-000011.jsonl"):
                return data + b"\n"
            return data

        with mock.patch.object(Path, "read_bytes", corrupted):
            with self.assertRaisesRegex(ValueError, "sealed archive file mismatch|sealed log changed"):
                audit.build_report()

    def test_frozen_source_digest_rejects_substitution(self) -> None:
        with mock.patch.dict(audit.SOURCE_HASHES,
                             {"agent/runner.py": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "frozen source missing or changed"):
                audit.source_contract()


if __name__ == "__main__":
    unittest.main()
