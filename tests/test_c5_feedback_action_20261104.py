"""Material archive-integrity and denominator checks for the action audit."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis import c5_feedback_action_20261104 as audit


class FeedbackActionAuditTests(unittest.TestCase):
    def test_verified_archives_support_stated_asymmetry(self) -> None:
        report = audit.build_report()
        self.assertEqual(report, json.loads(audit.OUT.read_text(encoding="utf-8")))
        by_arm = report["summary"]["by_arm"]
        self.assertEqual(by_arm["TRUTHFUL_PASS"]["first_inspect_pairs"], 0)
        self.assertEqual(by_arm["FALSE_FAIL"]["first_inspect_pairs"], 12)
        self.assertEqual(by_arm["FALSE_FAIL"]["inspections"], 24)
        self.assertEqual(by_arm["TRUTHFUL_PASS"]["submissions"], 28)
        self.assertEqual(by_arm["FALSE_FAIL"]["submissions"], 17)
        self.assertEqual(len(report["summary"]["false_inspection_families"]), 10)
        self.assertEqual(sum(p["arms"]["FALSE_FAIL"]["actions"] ==
                             ["INSPECT", "ATTEMPT", "INSPECT"] for p in report["pairs"]), 11)

    def test_changed_event_bytes_are_rejected_even_with_plausible_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            event = {"arm": "TRUTHFUL_PASS", "decision": 1, "kind": "ATTEMPT"}
            original = json.dumps(event) + "\n"
            events_path = path / "truthful_pass.events.jsonl"
            events_path.write_text(original)
            receipt = {"arm": "TRUTHFUL_PASS", "invalidated": False,
                       "eligible_for_main_analysis": False,
                       "event_sha256": hashlib.sha256(original.encode()).hexdigest(),
                       "decisions_used": 1, "terminal": "BUDGET"}
            (path / "truthful_pass.receipt.json").write_text(json.dumps(receipt))
            events_path.write_text(original + " ")
            with self.assertRaisesRegex(RuntimeError, "event bytes differ"):
                audit._events(path, "TRUTHFUL_PASS", expected_submissions=1)


if __name__ == "__main__":
    unittest.main()
