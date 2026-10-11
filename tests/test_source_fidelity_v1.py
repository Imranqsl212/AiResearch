"""Regression checks for the versioned, read-only historical source audit."""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from analysis.source_fidelity_v1 import ROOT, EXPERIMENT, build_report, classify_source
from experiments.trajectory_logger import _redact_text


class SourceFidelityV1Tests(unittest.TestCase):
    def test_logger_redaction_can_destroy_python_syntax(self) -> None:
        original = "def make_key():\n    token = bytes(range(16))\n    return token\n"
        ast.parse(original)
        logged = _redact_text(original)
        self.assertIn("token=<REDACTED>", logged)
        self.assertEqual(classify_source(logged)[0], "redaction_marker_syntax_error")
        self.assertNotEqual(ast.dump(ast.parse(original)), ast.dump(ast.parse(logged.replace("<REDACTED>", "'MASKED_VALUE'"))))

    @unittest.skipUnless((ROOT / "experiments" / "raw_archive" / EXPERIMENT / "archive_manifest.json").is_file(), "private sealed study archive unavailable")
    def test_historical_inventory_and_saved_report(self) -> None:
        report = build_report()
        summary = report["summary"]
        self.assertEqual(summary["runs"], 40)
        self.assertEqual(summary["logged_sources"], 77)
        self.assertEqual(summary["syntax_categories"], {
            "compound_statement_after_semicolon": 2,
            "parseable_logged_source": 63,
            "redaction_marker_syntax_error": 11,
            "unmatched_closing_brace": 1,
        })
        self.assertEqual(summary["adjacent_logged_source_pairs"], 37)
        self.assertEqual(summary["pairs_with_two_parseable_logged_sources"], 25)
        self.assertEqual(summary["called_api_inventory_change_pairs_in_parseable_subset"], 17)
        self.assertEqual(summary["final_logged_executed_source_hash_mismatches"], 2)
        self.assertEqual(
            json.loads((ROOT / "analysis" / "source_fidelity_v1.json").read_text(encoding="utf-8")),
            report,
        )
        # Audit output is safe to use as an index; it contains no candidate source.
        self.assertTrue(all("source" not in row for row in report["sources"]))


if __name__ == "__main__":
    unittest.main()
