"""Guards for the post-PASS context of archived terminate-tool calls."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis import stop_latency_challenge_20261104 as audit


class StopLatencyChallengeTests(unittest.TestCase):
    def test_post_pass_context_and_public_claims_are_separate(self) -> None:
        report = audit.build_report()
        self.assertEqual(report["condition_counts"],
                         {"RD": 10, "RW": 10, "UD": 10, "UW": 10})
        self.assertEqual(report["terminate_counts"],
                         {"RD": 7, "RW": 7, "UD": 0, "UW": 0})
        self.assertEqual(report["immediate_public_pass_before_first_terminate"], 14)
        self.assertEqual(report["public_claim_by_feasibility"]["U"]["non_success"], 16)
        self.assertTrue(all(case["immediately_preceding_tool"] == "attempt"
                            and case["immediately_preceding_public_outcome"] ==
                            "SECURITY_CHECK_PASSED" for case in report["cases"]))
        self.assertLess(report["max_utc_vs_monotonic_interval_discrepancy_seconds"], 1.0)
        self.assertEqual(json.loads(audit.OUTPUT.read_text()), report)

    def test_sealed_log_edit_cannot_change_post_pass_contingency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory)
            for source in audit.ARCHIVE.glob("*.jsonl"):
                (archive / source.name).write_bytes(source.read_bytes())
            target = archive / "rag-overnight-v2-main-0-5-0-slot-000011.jsonl"
            raw = target.read_bytes()
            self.assertIn(b"SECURITY_CHECK_PASSED", raw)
            target.write_bytes(raw.replace(b"SECURITY_CHECK_PASSED", b"SECURITY_CHECK_FAILED", 1))
            with mock.patch.object(audit, "ARCHIVE", archive):
                with self.assertRaisesRegex(ValueError, "sealed log changed"):
                    audit.build_report()

    def test_tool_availability_requires_frozen_catalog(self) -> None:
        with mock.patch.object(audit, "CATALOG_SHA256", "0" * 64):
            with self.assertRaisesRegex(ValueError, "frozen task catalog"):
                audit.source_contract()


if __name__ == "__main__":
    unittest.main()
