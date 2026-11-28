import json
import unittest

from analysis import replicate_display_report as report


class RepeatedDisplayTests(unittest.TestCase):
    def setUp(self):
        original = report.DEFAULT.parent / report.PARENT
        self.parent, self.cal = [json.loads((original / f).read_bytes()) for f in ("plan.json", "calibration.json")]
        self.plan = json.loads((report.DEFAULT / "plan.json").read_bytes())
        rows = []
        for b in self.plan["blocks"]:
            for a in report.ASSIGNMENTS:
                arm = a[:-1]
                rows.append({"parent_id": b["parent_id"], "assignment": a, "arm": arm, "model": b["model"],
                             "prompt_sha256": b["prompt_sha256"][arm], "before_correct": b["before_correct"],
                             "before_variant": b["before_variant"], "history_sha256": b["history_sha256"],
                             "status": "OK", "choice": "keep", "after_variant": b["before_variant"],
                             "after_correct": b["before_correct"]})
        self.data = {"rows": rows, "eligible_for_main_analysis": False}

    def verify(self):
        blocks, scores = report.verify_inputs(self.plan, self.parent, self.cal, self.data)
        return report.summarize(self.data["rows"], blocks, scores)

    def test_extremes_signs_and_identical_distributions(self):
        self.assertEqual(report.disagreement(("a", "b", "a", "b")), (2, 2, -2))
        self.assertEqual(report.disagreement(("a", "a", "b", "b")), (4, 0, 4))
        self.assertEqual(report.endpoint_summary((None,)*4, "abcd")["bound_quarters"], [-2, 4])
        self.assertEqual(report.endpoint_summary(("a", "a", "a", None), "abcd")["bound_quarters"], [0, 0])
        self.assertEqual(report.endpoint_summary(("a", "b", "c", None), "abcd")["bound_quarters"], [-1, 2])

    def test_same_source_and_literal_repetition_counts(self):
        s = self.verify()
        self.assertEqual(s["estimates"]["source"]["complete_mean"], 0)
        for arm in ("none", "shared"):
            self.assertEqual(s["cells"][arm]["preservation_passed"], 24)
            self.assertEqual(s["cells"][arm]["repair_scored"], 8)
        self.assertTrue(report.report(s).endswith("\n"))

    def test_partial_observations_tighten_scheduled_bounds(self):
        for row in self.data["rows"]:
            if row["assignment"] == "shared2":
                row.update(status="UNSTARTED", choice=None, after_variant=None, after_correct=None)
        s = self.verify()
        for e in report.ENDPOINTS:
            self.assertEqual(s["estimates"][e]["scheduled_bounds"], [0, 0])
            self.assertIsNone(s["estimates"][e]["complete_mean"])

    def test_missing_and_inconsistent_rows_fail(self):
        self.data["rows"][0]["choice"] = "not in menu"
        with self.assertRaisesRegex(ValueError, "grade"):
            self.verify()
        self.data["rows"].pop()
        with self.assertRaisesRegex(ValueError, "assignment"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
