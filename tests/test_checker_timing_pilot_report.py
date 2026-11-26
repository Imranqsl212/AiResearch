import copy
import unittest

from analysis.checker_timing_pilot_20261126 import render


def example(timing, state, results):
    start = "v1" if state == "correct" else "v0"
    current = start
    steps = []
    for n, after in enumerate(results, 1):
        steps.append({"decision": n, "status": "OK", "action": "keep" if current == after else after,
                      "before_variant": current, "after_variant": after, "correct_before": current == "v1",
                      "correct_after": after == "v1", "observed_diagnostic_before": n == 2 or timing == "early",
                      "seconds": 1.})
        current = after
    return {"model": "example", "case": "dateutil", "repeat": 1, "state": state, "timing": timing,
            "episode_id": timing + state, "start_variant": start, "steps": steps}


class TimingReportTest(unittest.TestCase):
    def setUp(self):
        self.data = {"roster": ["example"], "access": {"example": "OK"}, "plan_sha256": "sample",
                     "episodes": [example("early", "defective", ["v1", "v0"]),
                                  example("late", "defective", ["v0", "v1"]),
                                  example("early", "correct", ["v0", "v1"]),
                                  example("late", "correct", ["v1"])]}

    def test_count_paired_reversal_and_missing_second_choice_separately(self):
        report = render(self.data)
        for row in (
            "| example | dateutil | до | 1/1 | 0/1 | 1/1 | 0/1 |",
            "| example | dateutil | после | 0/1 | 1/1 | 0/1 | — |",
            "| 1 | Исправление | 1/4 | 1 | 0 | 0 |",
            "| 2 | Исправление | 1/4 | 0 | 1 | 0 |",
            "| 2 | Поломка | 0/4 | 0 | 0 | 0 |",
            "| до | 2 | 1 | 1 | 0 | 0 |",
        ):
            self.assertIn(row, report)

    def test_reject_duplicate_or_wrong_timing(self):
        data = copy.deepcopy(self.data)
        data["episodes"].append(data["episodes"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            render(data)
        self.data["episodes"][0]["steps"][0]["observed_diagnostic_before"] = False
        with self.assertRaisesRegex(ValueError, "wrong time"):
            render(self.data)

    def test_valid_rewrite_stays_preservation(self):
        row = self.data["episodes"][3]
        step = row["steps"][0]
        step["action"] = step["after_variant"] = "also-valid"
        report = render(self.data)
        self.assertIn("| example | dateutil | после | 0/1 | 1/1 | 0/1 | — |", report)
        self.assertIn("| example | dateutil | после | 1 | 0 | 1 | 0 |", report)
