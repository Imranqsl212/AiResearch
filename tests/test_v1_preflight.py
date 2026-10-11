"""Regression checks for the prospective main-run freeze gate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from reproduction.preflight import ROOT, validate_freeze


class V1PreflightTest(unittest.TestCase):
    def test_checked_in_draft_manifest_fails_closed(self) -> None:
        report = validate_freeze(ROOT / "experiment_manifest.json")
        self.assertFalse(report["passed"])
        self.assertTrue(any("not explicitly frozen" in error for error in report["errors"]))

    def test_unreadable_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text("{broken", encoding="utf-8")
            report = validate_freeze(path)
        self.assertFalse(report["passed"])
        self.assertTrue(any("unreadable" in error for error in report["errors"]))

    def test_changed_protocol_digest_fails_closed(self) -> None:
        original = json.loads((ROOT / "experiment_manifest.json").read_text(encoding="utf-8"))
        original["schema_version"] = "1.0"
        original["status"] = "FROZEN"
        original["main_run_permitted"] = True
        original["experiment"]["protocol_hash"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(original), encoding="utf-8")
            report = validate_freeze(path)
        self.assertFalse(report["passed"])
        self.assertIn("artifact digest mismatch: protocol_hash", report["errors"])


if __name__ == "__main__":
    unittest.main()
