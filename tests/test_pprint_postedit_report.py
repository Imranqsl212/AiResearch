import unittest

from analysis.pprint_postedit_report import render


def arm(parent, probe, before, after):
    return {"parent_id": parent, "model": "model", "probe": probe, "before_correct": before,
            "before_variant": "good" if before else "broken", "after_correct": after,
            "after_variant": "good" if after else ("broken" if after is not None else None),
            "choice": ("keep" if after == before else "v1") if after is not None else None,
            "status": "OK" if after is not None else "INVALID_RESPONSE"}


class PosteditReportTest(unittest.TestCase):
    def test_repair_preservation_and_incomplete_pair(self):
        rows = [arm("a", "1,2", False, False), arm("a", "2,10", False, True),
                arm("b", "1,2", True, True), arm("b", "2,10", True, False),
                arm("c", "1,2", False, True), arm("c", "2,10", False, None)]
        text = render({"plan_sha256": "abc", "rows": rows})
        self.assertIn("| Все модели | 1,2 | 3/3 | 1/2 | 1/1 | 0/1 |", text)
        self.assertIn("| Все модели | 2,10 | 2/3 | 1/1 | 0/1 | 1/1 |", text)
        self.assertIn("| Исправить поломку | 1/2 | 0 | 1 | 0 | 0 |", text)
        self.assertIn("| Сохранить рабочий код | 1/1 | 1 | 0 | 0 | 0 |", text)
        self.assertIn("INVALID_RESPONSE", text)

    def test_harmless_change_and_both_successful(self):
        left = arm("a", "1,2", True, True)
        left.update(after_variant="another-good", choice="v1")
        right = arm("a", "2,10", True, True)
        text = render({"rows": [left, right], "plan_sha256": "abc"})
        self.assertIn("| Сохранить рабочий код | 1/1 | 0 | 0 | 1 | 0 |", text)
        self.assertIn("| Все модели | 1,2 | 1/1 | — | 1/1 | 0/1 |", text)

    def test_mismatched_or_missing_arms_rejected(self):
        left = arm("a", "1,2", True, True)
        right = arm("a", "2,10", False, False)
        for rows in ([left], [left, right], [left, left]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                render({"rows": rows, "plan_sha256": "abc"})
