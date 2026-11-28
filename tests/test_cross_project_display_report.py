import copy
import json
import unittest

from analysis.cross_project_display_report import ARMS, DEFAULT, PRIOR, bound_json, grades, match_rows, render


def saved_inputs():
    plan = json.loads((DEFAULT / "plan.json").read_bytes())
    cal = bound_json(DEFAULT / "calibration.json", plan["calibration_sha256"])
    original = bound_json(DEFAULT.parent / "checker_timing_20261126" / "calibration.json", plan["source_sha256"][PRIOR])
    return plan, cal, original


def keep_everywhere(plan):
    rows = []
    for b in plan["blocks"]:
        for a in ARMS:
            row = {k: b[k] for k in ("parent_id", "project", "model", "before_variant",
                                      "before_correct", "history_sha256", "base_prompt_sha256")}
            row.update(arm=a, probe=a, prompt_sha256=b["prompt_sha256"][a], status="OK", choice="keep",
                       after_correct=b["before_correct"], after_variant=b["before_variant"])
            rows.append(row)
    return {"rows": rows}


class CrossProjectReportTest(unittest.TestCase):
    def test_independent_reference_and_project_specific_grades(self):
        _, cal, original = saved_inputs()
        scores = grades(cal, original)
        self.assertTrue(scores["cpython", "p7"])
        self.assertFalse(scores["dateutil", "p7"])
        altered = copy.deepcopy(cal)
        variants = altered["projects"]["dateutil"]["variants"]
        variants["t9"]["outputs"]["revealing"] = variants["k3"]["outputs"]["revealing"]
        with self.assertRaises(ValueError):
            grades(altered, original)
        cal["projects"]["cpp"] = cal["projects"].pop("cpython")
        with self.assertRaises(ValueError):
            grades(cal, original)

    def test_complete_pairs_and_an_unavailable_call(self):
        plan, cal, original = saved_inputs()
        scores = grades(cal, original)
        data = keep_everywhere(plan)
        row = next(r for r in data["rows"] if r["arm"] == "shared" and r["before_correct"])
        row.update(status="UNSTARTED", after_correct=None, choice=None, after_variant=None)
        matched = match_rows(plan, data, scores)
        text = render(matched, cal)
        self.assertIn("| No new output vs Shared | Working | 5/6 | 5 | 0 | 0 | 0 | 0/5 |", text)
        self.assertIn("| No new output vs Revealing | Faulty | 8/8 | 0 | 0 | 0 | 8 | 0/8 |", text)
        self.assertIn("UNSTARTED (1)", text)
        data["rows"].pop()
        with self.assertRaises(ValueError):
            match_rows(plan, data, scores)

    def test_digest_assignment_and_selection_must_match(self):
        plan, cal, original = saved_inputs()
        scores = grades(cal, original)
        data = keep_everywhere(plan)
        for field, value in (("choice", "invalid"), ("after_correct", None),
                             ("history_sha256", "new-prompt"), ("project", "third-project")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                incorrect = copy.deepcopy(data)
                incorrect["rows"][0][field] = value
                match_rows(plan, incorrect, scores)
