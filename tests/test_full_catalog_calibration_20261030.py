"""Integrity checks for the excluded 20-family finite catalog recount."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from analysis import full_catalog_calibration_20261030 as calibration


class FullCatalogCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = calibration.verify()

    def test_complete_excluded_catalog_and_separate_denominators(self) -> None:
        report = self.report
        self.assertEqual(report["status"], "EXCLUDED_AUTHORED_FINITE_CATALOG_CALIBRATION")
        self.assertEqual((report["family_count"], report["task_condition_count"],
                          report["independent_candidate_decisions_rechecked"]), (20, 100, 1820))
        self.assertEqual((report["eligible_main_episodes"], report["agent_submissions"]), (0, 0))
        self.assertIsNone(report["population_error_rate"])
        self.assertIsNone(report["causal_effect"])
        self.assertEqual(report["by_condition"]["C1"]["weak_pass_insecure"], 60)
        self.assertEqual(report["by_condition"]["C1"]["oracle_insecure"], 336)
        self.assertEqual(report["c1_families_with_weak_pass_insecure"], 18)
        self.assertEqual(report["by_condition"]["C5"]["gate_fail_secure"], 28)
        self.assertEqual(report["by_condition"]["C5"]["oracle_secure"], 28)
        self.assertEqual(report["catalog_summary"]["strong_insecure"], 345)
        self.assertEqual(report["catalog_summary"]["strong_pass_insecure"], 0)

    def test_csv_has_one_row_per_family_and_condition(self) -> None:
        path = calibration.ROOT / "analysis" / calibration.CSV_NAME
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 100)
        self.assertEqual(len({row["family"] for row in rows}), 20)
        self.assertEqual({row["condition"] for row in rows}, set(calibration.CONDITIONS))
        self.assertEqual(len({(row["family"], row["condition"]) for row in rows}), 100)
        self.assertEqual(sum(int(row["candidate_decisions"]) for row in rows), 1820)

    def test_modified_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / calibration.JSON_NAME
            csv_path = root / calibration.CSV_NAME
            json_path.write_bytes((calibration.ROOT / "analysis" / calibration.JSON_NAME).read_bytes())
            csv_path.write_bytes((calibration.ROOT / "analysis" / calibration.CSV_NAME).read_bytes())
            csv_path.write_text(csv_path.read_text(encoding="utf-8").replace(
                "authorization,C1,", "authorization,C1,999,", 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CSV differs"):
                calibration.verify(json_path, csv_path)


if __name__ == "__main__":
    unittest.main()
