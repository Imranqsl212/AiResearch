"""Source-identity and frozen-calibration checks; no candidate execution."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analysis.sast_mutation_join import SAST_PATH, build_report


class SASTMutationJoinTests(unittest.TestCase):
    def test_source_identical_eight_row_comparison(self) -> None:
        report = build_report()
        self.assertEqual(report["status"], "EXCLUDED_AUTHORED_CALIBRATION")
        self.assertFalse(report["eligible_for_main_analysis"])
        self.assertEqual(report["agent_submissions"], 0)
        self.assertEqual(report["coverage"]["joined_profiles"], 8)
        self.assertEqual(report["coverage"]["saved_docker_profiles"], 9)
        self.assertEqual(report["coverage"]["unjoined_saved_profiles"],
                         ["sqlite_lookup/uppercase_secure_reference"])
        self.assertEqual(report["mutation_summary"], {
            "authored_insecure_mutations": 4,
            "weak_rejections": 0,
            "strong_rejections": 4,
            "bandit_with_findings": 4,
        })
        self.assertEqual({(row["bandit_status"], row["weak_passed"],
                           row["strong_passed"]): row["count"]
                          for row in report["cross_tab"]}, {
            ("NO_FINDINGS", True, True): 2,
            ("FINDINGS", False, False): 2,
            ("FINDINGS", True, False): 4,
        })

    def test_substituted_source_hash_rejected(self) -> None:
        data = json.loads(SAST_PATH.read_text(encoding="utf-8"))
        data["examples"][0]["source_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(prefix="sast-join-test-") as folder:
            path = Path(folder) / "modified.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Bandit/source identity"):
                build_report(sast_path=path)

    def test_duplicate_bandit_profile_rejected(self) -> None:
        data = json.loads(SAST_PATH.read_text(encoding="utf-8"))
        data["examples"][-1] = data["examples"][0]
        with tempfile.TemporaryDirectory(prefix="sast-join-test-") as folder:
            path = Path(folder) / "modified.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate Bandit example"):
                build_report(sast_path=path)


if __name__ == "__main__":
    unittest.main()
