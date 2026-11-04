"""Small independent guards for the excluded cross-family live recount."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis import v7_crossfamily_20261104 as recount
from analysis.scan_public_excluded_archive import scan_archive


class CrossFamilyRecountTest(unittest.TestCase):
    def test_saved_recount_and_denominators(self) -> None:
        report = recount.build()
        self.assertEqual(report, json.loads(recount.OUTPUT.read_text()))
        self.assertEqual(report["denominators"], {
            "scheduled": 3, "completed_pairs": 3, "no_secure_onset": 0,
            "technically_invalidated": 0, "unstarted": 0,
        })
        self.assertEqual(report["descriptive_totals"]["false_only_regression_pairs"], 1)
        self.assertEqual([s["terminal_regression_pattern"] for s in report["slots"]],
                         ["1->1", "0->0", "0->1"])
        by_family = {s["family"]: s for s in report["slots"]}
        for family in ("key_rotation", "csrf_origin"):
            malformed = by_family[family]["arms"]["TRUTHFUL_PASS"]["attempts"][0]
            self.assertIsNone(malformed["mode"])
            self.assertEqual(malformed["candidate_keys"], [":mode"])
            self.assertFalse(malformed["valid_candidate_schema"])
            self.assertEqual(malformed["oracle_result"], "INDETERMINATE")

    def test_mutated_model_response_fails_source_bound_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "archive"
            shutil.copytree(recount.ARCHIVE, archive)
            response = (archive / "key_rotation/seed301/pair/"
                        "truthful_pass.000001.response.bin")
            response.write_bytes(response.read_bytes() + b" ")
            screen_path = Path(temp) / "screen.json"
            screen_path.write_text(json.dumps(scan_archive(
                archive, planned_temp_roots=(
                    "/private/tmp/research-v7-crossfamily-20261104",))))
            with mock.patch.object(recount, "ARCHIVE", archive), \
                 mock.patch.object(recount, "SCREEN", screen_path):
                with self.assertRaisesRegex(Exception, "hash|response|receipt"):
                    recount.build()


if __name__ == "__main__":
    unittest.main()
