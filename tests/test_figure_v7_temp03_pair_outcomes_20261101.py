"""Category and missing-data tests for the two-wave excluded figure."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from analysis import figure_v7_temp03_pair_outcomes_20261101 as figure
from analysis import v7_temp_variance_20261101 as v1


def _pair_slot(truth: int | None, false: int | None) -> dict:
    return {
        "status": "COMPLETED_EXCLUDED_C5_PAIR",
        "pair": {"arms": {
            "TRUTHFUL_PASS": {"terminal_finite_property_regression": truth},
            "FALSE_FAIL": {"terminal_finite_property_regression": false},
        }},
    }


class V7Temp03FigureTests(unittest.TestCase):
    def test_all_paired_outcomes_have_distinct_categories(self) -> None:
        cases = {
            (0, 1): "FALSE_ONLY", (1, 0): "TRUTH_ONLY",
            (1, 1): "BOTH", (0, 0): "NEITHER",
            (None, 1): "INDETERMINATE", (0, None): "INDETERMINATE",
        }
        for endpoints, expected in cases.items():
            with self.subTest(endpoints=endpoints):
                self.assertEqual(figure.category(_pair_slot(*endpoints)), expected)

    def test_no_onset_technical_and_unstarted_remain_distinct(self) -> None:
        self.assertEqual(figure.category({
            "status": "NOT_RUN_NO_ONSET", "precursor": {"verified_status": "example"},
            "pair": None}), "NO_ONSET")
        for status in ("PRECURSOR_INVALIDATED", "PAIR_INVALIDATED",
                       "POST_PRECURSOR_INVALIDATED"):
            self.assertEqual(figure.category({"status": status, "pair": None}),
                             "TECHNICAL")
        self.assertEqual(figure.category({
            "status": "NOT_RUN_AFTER_STOP", "precursor": None, "pair": None}),
            "UNSTARTED")
        with self.assertRaisesRegex(RuntimeError, "neither 0, 1, nor null"):
            figure.category(_pair_slot(True, 0))

    def test_grid_accounts_for_all_32_fixed_slots(self) -> None:
        schedule = v1.fixed_schedule()
        slots = [{
            "slot_id": row["slot_id"], "family": row["family"],
            "precursor_seed": row["precursor_seed"],
            "branch_seed": row["branch_seed"],
            "status": "NOT_RUN_AFTER_STOP", "precursor": None, "pair": None,
        } for row in schedule]
        report = {
            "schema_version": "excluded-v7-temp03-four-seed-20261101-1",
            "eligible_for_main_analysis": False,
            "dispatch_status": "WAVE_STOPPED",
            "overall": {"scheduled_precursors": 32}, "slots": slots,
        }
        matrix = figure.grid(report, schedule, report["schema_version"])
        self.assertEqual(len(matrix), 8)
        self.assertEqual(sum(len(row) for row in matrix), 32)
        self.assertEqual({cell for row in matrix for cell in row}, {"UNSTARTED"})
        report["slots"] = slots[:-1]
        with self.assertRaisesRegex(RuntimeError, "all 32"):
            figure.grid(report, schedule, report["schema_version"])

    def test_missing_v2_report_fails_before_archive_replay_or_png(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "v1.json"
            second = Path(directory) / "v2-missing.json"
            first.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "verified report missing"):
                figure.build_figure_data(first, second)
            self.assertFalse(second.exists())

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow is not installed")
    def test_renderer_draws_a_complete_png_in_temporary_directory(self) -> None:
        from PIL import Image
        data = {"families": list(v1.FAMILIES), "waves": [
            {"label": "Wave 1: excluded", "seeds": list(v1.SEEDS),
             "dispatch_status": "WAVE_STOPPED",
             "matrix": [["UNSTARTED"] * 4 for _ in v1.FAMILIES]},
            {"label": "Wave 2: post-failure excluded", "seeds": [201, 202, 203, 204],
             "dispatch_status": "WAVE_COMPLETE",
             "matrix": [["NEITHER"] * 4 for _ in v1.FAMILIES]},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "synthetic-fixture.png"
            figure.render_png(data, output)
            with Image.open(output) as image:
                self.assertEqual(image.size, (2500, 1450))
                self.assertEqual(image.format, "PNG")


if __name__ == "__main__":
    unittest.main()
